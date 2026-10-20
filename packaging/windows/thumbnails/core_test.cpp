// Test for thumbcore on any system:  core_test <file> <out-file> [size]
// Writes the embedded picture (PNG/JPEG) or, for STL, a PAM image (RGBA).
#include "thumbcore.h"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>

int main(int argc, char** argv) {
    if (argc < 3) { std::fprintf(stderr, "usage: core_test <file> <out> [size]\n"); return 2; }
    std::ifstream f(argv[1], std::ios::binary);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    pv3d::MemorySource src(data.data(), data.size());
    int size = argc > 3 ? std::atoi(argv[3]) : 256;
    std::vector<uint8_t> out;
    const char* kinds[] = {"unknown", "zip", "gcode", "stl"};
    pv3d::Kind k = pv3d::detect(src);
    bool ok = false;
    std::FILE* o = std::fopen(argv[2], "wb");
    if (k == pv3d::Kind::Zip) ok = pv3d::zip_thumbnail(src, out);
    if (k == pv3d::Kind::Gcode) ok = pv3d::gcode_thumbnail(src, out);
    if (k == pv3d::Kind::Stl) {
        ok = pv3d::render_stl(src, size, out);
        if (ok) std::fprintf(o, "P7\nWIDTH %d\nHEIGHT %d\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n", size, size);
    }
    if (ok) std::fwrite(out.data(), 1, out.size(), o);
    std::fclose(o);
    std::printf("%s: %s, %s, %zu bytes\n", argv[1], kinds[int(k)], ok ? "OK" : "no thumbnail", out.size());
    return ok ? 0 : 1;
}
