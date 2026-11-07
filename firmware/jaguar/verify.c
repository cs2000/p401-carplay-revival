/* SPDX-License-Identifier: MIT
 * Read-only startup integrity check. CRC32 is IEEE/zlib, not authentication.
 * Interface: verify verify FILE CRCHEX LENGTH
 * Symlinks are followed deliberately: vendor ABI libraries use SONAME aliases.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int parse_crc(const char *text, uint32_t *result)
{
    uint32_t value = 0;
    unsigned int i;
    for (i = 0; i < 8; ++i) {
        unsigned char c = (unsigned char)text[i];
        unsigned int digit;
        if (c >= '0' && c <= '9') digit = (unsigned int)(c - '0');
        else if (c >= 'a' && c <= 'f') digit = (unsigned int)(c - 'a') + 10u;
        else if (c >= 'A' && c <= 'F') digit = (unsigned int)(c - 'A') + 10u;
        else return 0;
        value = (value << 4) | digit;
    }
    if (text[8] != '\0') return 0;
    *result = value;
    return 1;
}

static int parse_length(const char *text, uint64_t *result)
{
    uint64_t value = 0;
    if (*text == '\0') return 0;
    do {
        unsigned char c = (unsigned char)*text++;
        unsigned int digit;
        if (c < '0' || c > '9') return 0;
        digit = (unsigned int)(c - '0');
        if (value > UINT64_MAX / 10u ||
            (value == UINT64_MAX / 10u && digit > UINT64_MAX % 10u)) return 0;
        value = value * 10u + digit;
    } while (*text != '\0');
    *result = value;
    return 1;
}

int main(int argc, char **argv)
{
    uint32_t expected_crc;
    uint64_t expected_length;
    uint32_t crc = UINT32_C(0xffffffff);
    uint64_t total = 0;
    unsigned char buffer[8192];
    struct stat info;
    int fd;

    if (argc != 5 || strcmp(argv[1], "verify") != 0 ||
        !parse_crc(argv[3], &expected_crc) ||
        !parse_length(argv[4], &expected_length)) return 2;

    /* O_NONBLOCK also prevents a bad path to a FIFO from stalling startup. */
    fd = open(argv[2], O_RDONLY | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) return 1;
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size < 0 ||
        (uint64_t)info.st_size != expected_length) {
        close(fd);
        return 1;
    }
    for (;;) {
        ssize_t count = read(fd, buffer, sizeof(buffer));
        ssize_t i;
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) { close(fd); return 1; }
        if (count == 0) break;
        if ((uint64_t)count > expected_length - total) {
            close(fd);
            return 1;
        }
        total += (uint64_t)count;
        for (i = 0; i < count; ++i) {
            unsigned int bit;
            crc ^= buffer[i];
            for (bit = 0; bit < 8; ++bit)
                crc = (crc >> 1) ^ ((0u - (crc & 1u)) & UINT32_C(0xedb88320));
        }
    }
    if (close(fd) != 0) return 1;
    crc ^= UINT32_C(0xffffffff);
    return total == expected_length && crc == expected_crc ? 0 : 1;
}
