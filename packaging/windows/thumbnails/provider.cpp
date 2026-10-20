// PrintView3D thumbnails for Windows File Explorer.
//
// A standard thumbnail provider (IThumbnailProvider + IInitializeWithStream).
// Windows runs it in a separate helper process, so a bad file can never crash
// Explorer itself. The installer registers it per user for .3mf, .fcstd,
// .gcode, .gco and .stl (HKCU\Software\Classes\SystemFileAssociations\<ext>\ShellEx).
//
//   3MF / FCStd / G-code: the preview picture saved in the file (decoded with WIC)
//   STL: drawn by thumbcore (no picture is stored in STL files)

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <new>
#include <shlwapi.h>
#include <thumbcache.h>
#include <wincodec.h>

#include "thumbcore.h"

// {64535B54-55A8-4412-919A-88F46D3E3B86}
static const CLSID CLSID_PrintView3DThumbnails =
    {0x64535b54, 0x55a8, 0x4412, {0x91, 0x9a, 0x88, 0xf4, 0x6d, 0x3e, 0x3b, 0x86}};

static long g_objects = 0;
static long g_locks = 0;

namespace {

// IStream as a thumbcore Source.
struct StreamSource : pv3d::Source {
    IStream* s;
    uint64_t n = 0;
    explicit StreamSource(IStream* st) : s(st) {
        STATSTG st_ = {};
        if (SUCCEEDED(s->Stat(&st_, STATFLAG_NONAME))) n = st_.cbSize.QuadPart;
    }
    uint64_t size() override { return n; }
    bool read(uint64_t off, void* buf, size_t len) override {
        if (off > n || len > n - off) return false;
        LARGE_INTEGER li;
        li.QuadPart = LONGLONG(off);
        if (FAILED(s->Seek(li, STREAM_SEEK_SET, nullptr))) return false;
        BYTE* p = static_cast<BYTE*>(buf);
        while (len > 0) {
            ULONG chunk = ULONG(len > (1u << 30) ? (1u << 30) : len), got = 0;
            if (FAILED(s->Read(p, chunk, &got)) || got == 0) return false;
            p += got;
            len -= got;
        }
        return true;
    }
};

// 32-bit top-down DIB with premultiplied alpha, as Explorer wants it.
HBITMAP make_bitmap(int w, int h, BYTE** bits) {
    BITMAPINFO bi = {};
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = -h;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    void* p = nullptr;
    HBITMAP b = CreateDIBSection(nullptr, &bi, DIB_RGB_COLORS, &p, nullptr, 0);
    *bits = static_cast<BYTE*>(p);
    return b;
}

// PNG / JPEG bytes -> HBITMAP no larger than cx, keeping the aspect ratio.
HRESULT decode_image(const std::vector<uint8_t>& img, UINT cx, HBITMAP* out) {
    IWICImagingFactory* f = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&f));
    if (FAILED(hr)) return hr;
    IStream* mem = SHCreateMemStream(img.data(), UINT(img.size()));
    IWICBitmapDecoder* dec = nullptr;
    IWICBitmapFrameDecode* frame = nullptr;
    IWICBitmapScaler* sc = nullptr;
    IWICFormatConverter* cv = nullptr;
    hr = mem ? S_OK : E_OUTOFMEMORY;
    if (SUCCEEDED(hr)) hr = f->CreateDecoderFromStream(mem, nullptr, WICDecodeMetadataCacheOnDemand, &dec);
    if (SUCCEEDED(hr)) hr = dec->GetFrame(0, &frame);
    UINT w = 0, h = 0;
    if (SUCCEEDED(hr)) hr = frame->GetSize(&w, &h);
    if (SUCCEEDED(hr) && (w == 0 || h == 0)) hr = E_FAIL;
    UINT tw = w, th = h;
    if (SUCCEEDED(hr) && (w > cx || h > cx)) {
        if (w >= h) { tw = cx; th = UINT(std::max(1.0, double(h) * cx / w)); }
        else { th = cx; tw = UINT(std::max(1.0, double(w) * cx / h)); }
    }
    if (SUCCEEDED(hr)) hr = f->CreateBitmapScaler(&sc);
    if (SUCCEEDED(hr)) hr = sc->Initialize(frame, tw, th, WICBitmapInterpolationModeFant);
    if (SUCCEEDED(hr)) hr = f->CreateFormatConverter(&cv);
    if (SUCCEEDED(hr)) hr = cv->Initialize(sc, GUID_WICPixelFormat32bppPBGRA, WICBitmapDitherTypeNone,
                                           nullptr, 0.0, WICBitmapPaletteTypeCustom);
    if (SUCCEEDED(hr)) {
        BYTE* bits = nullptr;
        HBITMAP b = make_bitmap(int(tw), int(th), &bits);
        hr = b ? cv->CopyPixels(nullptr, tw * 4, tw * th * 4, bits) : E_OUTOFMEMORY;
        if (SUCCEEDED(hr)) *out = b;
        else if (b) DeleteObject(b);
    }
    if (cv) cv->Release();
    if (sc) sc->Release();
    if (frame) frame->Release();
    if (dec) dec->Release();
    if (mem) mem->Release();
    f->Release();
    return hr;
}

class Provider : public IThumbnailProvider, public IInitializeWithStream {
    long refs_ = 1;
    IStream* stream_ = nullptr;

public:
    Provider() { InterlockedIncrement(&g_objects); }
    virtual ~Provider() {
        if (stream_) stream_->Release();
        InterlockedDecrement(&g_objects);
    }

    // IUnknown
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_IThumbnailProvider)
            *ppv = static_cast<IThumbnailProvider*>(this);
        else if (riid == IID_IInitializeWithStream)
            *ppv = static_cast<IInitializeWithStream*>(this);
        else {
            *ppv = nullptr;
            return E_NOINTERFACE;
        }
        AddRef();
        return S_OK;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return ULONG(InterlockedIncrement(&refs_)); }
    IFACEMETHODIMP_(ULONG) Release() override {
        long r = InterlockedDecrement(&refs_);
        if (r == 0) delete this;
        return ULONG(r);
    }

    // IInitializeWithStream
    IFACEMETHODIMP Initialize(IStream* s, DWORD) override {
        if (stream_) return HRESULT_FROM_WIN32(ERROR_ALREADY_INITIALIZED);
        if (!s) return E_INVALIDARG;
        stream_ = s;
        stream_->AddRef();
        return S_OK;
    }

    // IThumbnailProvider
    IFACEMETHODIMP GetThumbnail(UINT cx, HBITMAP* phbmp, WTS_ALPHATYPE* alpha) override {
        if (!phbmp || !alpha || !stream_) return E_INVALIDARG;
        *phbmp = nullptr;
        if (cx < 16) cx = 16;
        if (cx > 1024) cx = 1024;
        try {
            StreamSource src(stream_);
            std::vector<uint8_t> data;
            switch (pv3d::detect(src)) {
                case pv3d::Kind::Zip:
                    if (!pv3d::zip_thumbnail(src, data)) return E_FAIL;
                    *alpha = WTSAT_ARGB;
                    return decode_image(data, cx, phbmp);
                case pv3d::Kind::Gcode:
                    if (!pv3d::gcode_thumbnail(src, data)) return E_FAIL;
                    *alpha = WTSAT_ARGB;
                    return decode_image(data, cx, phbmp);
                case pv3d::Kind::Stl: {
                    if (!pv3d::render_stl(src, int(cx), data)) return E_FAIL;
                    BYTE* bits = nullptr;
                    HBITMAP b = make_bitmap(int(cx), int(cx), &bits);
                    if (!b) return E_OUTOFMEMORY;
                    for (size_t i = 0; i < size_t(cx) * cx; ++i) {      // RGBA -> premultiplied BGRA
                        const uint8_t* s = &data[i * 4];
                        unsigned a = s[3];
                        bits[i * 4 + 0] = BYTE(s[2] * a / 255);
                        bits[i * 4 + 1] = BYTE(s[1] * a / 255);
                        bits[i * 4 + 2] = BYTE(s[0] * a / 255);
                        bits[i * 4 + 3] = BYTE(a);
                    }
                    *phbmp = b;
                    *alpha = WTSAT_ARGB;
                    return S_OK;
                }
                default:
                    return E_FAIL;
            }
        } catch (...) {     // out of memory or anything unexpected: no thumbnail, never a crash
            if (*phbmp) { DeleteObject(*phbmp); *phbmp = nullptr; }
            return E_FAIL;
        }
    }
};

class Factory : public IClassFactory {
public:
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_IClassFactory) {
            *ppv = static_cast<IClassFactory*>(this);
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }
    IFACEMETHODIMP_(ULONG) AddRef() override { return 2; }
    IFACEMETHODIMP_(ULONG) Release() override { return 1; }
    IFACEMETHODIMP CreateInstance(IUnknown* outer, REFIID riid, void** ppv) override {
        if (!ppv) return E_POINTER;
        *ppv = nullptr;
        if (outer) return CLASS_E_NOAGGREGATION;
        Provider* p = new (std::nothrow) Provider();
        if (!p) return E_OUTOFMEMORY;
        HRESULT hr = p->QueryInterface(riid, ppv);
        p->Release();
        return hr;
    }
    IFACEMETHODIMP LockServer(BOOL lock) override {
        if (lock) InterlockedIncrement(&g_locks);
        else InterlockedDecrement(&g_locks);
        return S_OK;
    }
};

Factory g_factory;

}  // namespace

STDAPI DllGetClassObject(REFCLSID clsid, REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    *ppv = nullptr;
    if (clsid != CLSID_PrintView3DThumbnails) return CLASS_E_CLASSNOTAVAILABLE;
    return g_factory.QueryInterface(riid, ppv);
}

STDAPI DllCanUnloadNow() { return (g_objects == 0 && g_locks == 0) ? S_OK : S_FALSE; }

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(module);
    return TRUE;
}
