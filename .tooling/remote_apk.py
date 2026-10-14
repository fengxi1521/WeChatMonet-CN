#!/usr/bin/env python3
"""Fetch only needed entries from a remote zip/APK using curl range requests."""
import io
import subprocess
import sys
import zipfile

URL = sys.argv[1]
ENTRIES = sys.argv[2:]  # entry names to extract, or "LIST"


class CurlFile(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        self.pos = 0
        self.total = self._length()

    def _length(self):
        out = subprocess.run(
            ["curl", "-fsIL", "--max-time", "120", "-o", "/dev/null",
             "-w", "%{size_download} %{http_code} %{url_effective}", self.url],
            capture_output=True, text=True).stdout.strip()
        # use header content-length via -I: parse last content-length
        out2 = subprocess.run(
            ["curl", "-fsIL", "--max-time", "120", self.url],
            capture_output=True, text=True).stdout
        lengths = [int(l.split(":", 1)[1].strip()) for l in out2.splitlines()
                   if l.lower().startswith("content-length:")]
        if not lengths:
            raise RuntimeError("no content-length: " + out + "|" + out2[:400])
        return max(lengths)

    def _range(self, start, end):
        for attempt in range(5):
            p = subprocess.run(
                ["curl", "-fsL", "--max-time", "300", "--retry", "3",
                 "-r", f"{start}-{end}", self.url],
                capture_output=True)
            if p.returncode == 0 and p.stdout:
                return p.stdout
        raise RuntimeError(f"range {start}-{end} failed")

    def readable(self):
        return True

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        elif whence == 2:
            self.pos = self.total + offset
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.total - self.pos
        if n == 0 or self.pos >= self.total:
            return b""
        end = min(self.pos + n, self.total) - 1
        data = self._range(self.pos, end)
        self.pos += len(data)
        return data


def main():
    f = CurlFile(URL)
    print(f"remote size = {f.total} bytes", file=sys.stderr)
    zf = zipfile.ZipFile(f)
    if not ENTRIES or ENTRIES[0] == "LIST":
        for i in zf.infolist():
            print(f"{i.header_offset:>12} {i.file_size:>12} {i.compress_size:>10} {i.compress_type} {i.filename}")
        return
    for name in ENTRIES:
        data = zf.read(name)
        out = name.replace("/", "_")
        with open(out, "wb") as fh:
            fh.write(data)
        print(f"wrote {out} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
