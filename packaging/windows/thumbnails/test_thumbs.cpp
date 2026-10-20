// Windows test for the thumbnail provider (run by GitHub Actions).
//   test_thumbs dll <provider.dll> <file>...   load the DLL directly and make 256 px thumbnails
//   test_thumbs shell <file>...                ask Windows' shell, i.e. what Explorer gets
// Every thumbnail must exist and contain visible pixels; it is also saved as <file>.thumb.png.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <shobjidl.h>
#include <thumbcache.h>
#include <wincodec.h>
#include <cstdio>
#include <string>

static const CLSID CLSID_PV3D = {0x64535b54, 0x55a8, 0x4412, {0x91, 0x9a, 0x88, 0xf4, 0x6d, 0x3e, 0x3b, 0x86}};

static bool check_and_save(HBITMAP b, const std::wstring& out) {
    DIBSECTION ds = {};
    BITMAP bm = {};
    if (!GetObjectW(b, sizeof bm, &bm)) return false;
    int w = bm.bmWidth, h = abs(bm.bmHeight);
    std::string px(size_t(w) * h * 4, '\0');
    BITMAPINFO bi = {};
    bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bi.bmiHeader.biWidth = w;
    bi.bmiHeader.biHeight = -h;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    HDC dc = GetDC(nullptr);
    GetDIBits(dc, b, 0, UINT(h), &px[0], &bi, DIB_RGB_COLORS);
    ReleaseDC(nullptr, dc);
    long visible = 0;
    for (size_t i = 0; i < size_t(w) * h; ++i)
        if ((unsigned char)px[i * 4 + 3] > 0 || px[i * 4] || px[i * 4 + 1] || px[i * 4 + 2]) ++visible;
    std::printf("  %dx%d, %ld visible pixels\n", w, h, visible);
    IWICImagingFactory* f = nullptr;
    if (SUCCEEDED(CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&f)))) {
        IWICBitmap* wb = nullptr;
        IWICStream* st = nullptr;
        IWICBitmapEncoder* enc = nullptr;
        IWICBitmapFrameEncode* fr = nullptr;
        if (SUCCEEDED(f->CreateBitmapFromHBITMAP(b, nullptr, WICBitmapUsePremultipliedAlpha, &wb)) &&
            SUCCEEDED(f->CreateStream(&st)) && SUCCEEDED(st->InitializeFromFilename(out.c_str(), GENERIC_WRITE)) &&
            SUCCEEDED(f->CreateEncoder(GUID_ContainerFormatPng, nullptr, &enc)) &&
            SUCCEEDED(enc->Initialize(st, WICBitmapEncoderNoCache)) && SUCCEEDED(enc->CreateNewFrame(&fr, nullptr)) &&
            SUCCEEDED(fr->Initialize(nullptr)) && SUCCEEDED(fr->WriteSource(wb, nullptr))) {
            fr->Commit();
            enc->Commit();
        }
        if (fr) fr->Release();
        if (enc) enc->Release();
        if (st) st->Release();
        if (wb) wb->Release();
        f->Release();
    }
    return w > 0 && h > 0 && visible > w * h / 50;
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 3) return 2;
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    bool shell = std::wstring(argv[1]) == L"shell";
    int first = shell ? 2 : 3, failed = 0;
    IClassFactory* factory = nullptr;
    if (!shell) {
        HMODULE dll = LoadLibraryW(argv[2]);
        auto get = dll ? (HRESULT(WINAPI*)(REFCLSID, REFIID, void**))GetProcAddress(dll, "DllGetClassObject") : nullptr;
        if (!get || FAILED(get(CLSID_PV3D, IID_PPV_ARGS(&factory)))) { std::printf("cannot load provider\n"); return 1; }
    }
    for (int i = first; i < argc; ++i) {
        wchar_t full[MAX_PATH];
        GetFullPathNameW(argv[i], MAX_PATH, full, nullptr);
        std::wprintf(L"%ls\n", full);
        HBITMAP b = nullptr;
        HRESULT hr;
        if (shell) {
            // Which thumbnail handler Windows picks for this file type.
            wchar_t clsid[64] = L"(none)";
            DWORD n = 64;
            AssocQueryStringW(ASSOCF_INIT_DEFAULTTOSTAR, ASSOCSTR_SHELLEXTENSION, PathFindExtensionW(full),
                              L"{e357fccd-a995-4576-b01f-234630154e96}", clsid, &n);
            std::wprintf(L"  handler %ls%ls\n", clsid, _wcsicmp(clsid, L"{64535B54-55A8-4412-919A-88F46D3E3B86}") ? L" (not PrintView3D)" : L"");
            IShellItemImageFactory* sf = nullptr;
            hr = SHCreateItemFromParsingName(full, nullptr, IID_PPV_ARGS(&sf));
            if (SUCCEEDED(hr)) {
                SIZE sz = {256, 256};
                hr = sf->GetImage(sz, SIIGBF_THUMBNAILONLY, &b);
                sf->Release();
            }
        } else {
            IThumbnailProvider* tp = nullptr;
            IInitializeWithStream* iw = nullptr;
            IStream* st = nullptr;
            WTS_ALPHATYPE at;
            hr = factory->CreateInstance(nullptr, IID_PPV_ARGS(&tp));
            if (SUCCEEDED(hr)) hr = tp->QueryInterface(IID_PPV_ARGS(&iw));
            if (SUCCEEDED(hr)) hr = SHCreateStreamOnFileEx(full, STGM_READ | STGM_SHARE_DENY_NONE, 0, FALSE, nullptr, &st);
            if (SUCCEEDED(hr)) hr = iw->Initialize(st, STGM_READ);
            if (SUCCEEDED(hr)) hr = tp->GetThumbnail(256, &b, &at);
            if (st) st->Release();
            if (iw) iw->Release();
            if (tp) tp->Release();
        }
        if (FAILED(hr) || !b || !check_and_save(b, std::wstring(full) + L".thumb.png")) {
            std::printf("  FAILED (0x%08lx)\n", (unsigned long)hr);
            ++failed;
        }
        if (b) DeleteObject(b);
    }
    if (factory) factory->Release();
    CoUninitialize();
    std::printf(failed ? "%d thumbnail(s) FAILED\n" : "all thumbnails OK\n", failed);
    return failed ? 1 : 0;
}
