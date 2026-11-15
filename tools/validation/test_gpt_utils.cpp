//Synthetic GPT regression tests. All library disk I/O is replaced below.
#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <linux/fs.h>
#include <limits.h>
#include <dirent.h>
#include <linux/kernel.h>
#include <asm/byteorder.h>
#include <inttypes.h>
#include <zlib.h>
#include <endian.h>
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <functional>
#include <map>
#include <string>
#include <vector>

static std::vector<uint8_t> image;
static uint32_t sector_size;
static size_t position;
static size_t chunk_size;
static size_t read_limit;
static size_t bytes_read;
static unsigned read_interrupts, write_interrupts, seek_interrupts, sync_interrupts;
static unsigned write_calls, sync_calls, open_calls, sync_fail_on_call;
static unsigned rejected_images;
static bool zero_write, read_error, write_error, sync_error, seek_error;
static const int fake_fd = 42;

static int fake_open(const char *path, int flags, ...)
{
    assert(!strcmp(path, "/dev/block/mmcblk0"));
    ++open_calls;
    return fake_fd;
}

static int fake_close(int fd)
{
    assert(fd == fake_fd);
    return 0;
}

static off64_t fake_lseek64(int fd, off64_t offset, int whence)
{
    assert(fd == fake_fd);
    if (seek_interrupts) {
        --seek_interrupts;
        errno = EINTR;
        return -1;
    }
    if (seek_error) {
        errno = EIO;
        return -1;
    }
    assert(whence == SEEK_SET || whence == SEEK_END);
    if (whence == SEEK_END)
        offset += image.size();
    if (offset < 0) {
        errno = EINVAL;
        return -1;
    }
    position = offset;
    return offset;
}

static ssize_t fake_read(int fd, void *buffer, size_t length)
{
    assert(fd == fake_fd);
    if (read_interrupts) {
        --read_interrupts;
        errno = EINTR;
        return -1;
    }
    if (read_error) {
        errno = EIO;
        return -1;
    }
    if (position >= image.size() || bytes_read >= read_limit)
        return 0;
    size_t done = std::min({length, chunk_size, image.size() - position,
                           read_limit - bytes_read});
    memcpy(buffer, image.data() + position, done);
    position += done;
    bytes_read += done;
    return done;
}

static ssize_t fake_write(int fd, const void *buffer, size_t length)
{
    assert(fd == fake_fd);
    ++write_calls;
    if (write_interrupts) {
        --write_interrupts;
        errno = EINTR;
        return -1;
    }
    if (write_error || position >= image.size()) {
        errno = EIO;
        return -1;
    }
    if (zero_write)
        return 0;
    size_t done = std::min({length, chunk_size, image.size() - position});
    memcpy(image.data() + position, buffer, done);
    position += done;
    return done;
}

static int fake_fsync(int fd)
{
    assert(fd == fake_fd);
    ++sync_calls;
    if (sync_interrupts) {
        --sync_interrupts;
        errno = EINTR;
        return -1;
    }
    if (sync_error || sync_calls == sync_fail_on_call) {
        errno = EIO;
        return -1;
    }
    return 0;
}

static int fake_ioctl(int fd, unsigned long request, ...)
{
    assert(fd == fake_fd && request == BLKSSZGET);
    va_list args;
    va_start(args, request);
    *va_arg(args, uint32_t *) = sector_size;
    va_end(args);
    return 0;
}

#define open fake_open
#define close fake_close
#define lseek64 fake_lseek64
#define read fake_read
#define write fake_write
#define fsync fake_fsync
#define ioctl fake_ioctl
#undef _LARGEFILE64_SOURCE
#if defined(__GNUC__) && !defined(__clang__)
//GCC diagnoses an existing snprintf in the unrelated SCSI path.
#pragma GCC diagnostic push
#pragma GCC diagnostic warning "-Wformat-truncation"
#endif
#include "../../gpt-utils/gpt-utils.cpp"
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic pop
#endif
#undef open
#undef close
#undef lseek64
#undef read
#undef write
#undef fsync
#undef ioctl

int32_t set_boot_lun(char *, uint8_t)
{
    assert(false && "UFS device operations are forbidden in these tests");
    return -1;
}

static void reset_io()
{
    position = bytes_read = 0;
    chunk_size = read_limit = SIZE_MAX;
    read_interrupts = write_interrupts = seek_interrupts = sync_interrupts = 0;
    write_calls = sync_calls = open_calls = sync_fail_on_call = 0;
    zero_write = read_error = write_error = sync_error = seek_error = false;
}

static void put32(uint8_t *data, uint32_t value)
{
    PUT_4_BYTES(data, value);
}

static void put64(uint8_t *data, uint64_t value)
{
    put32(data, value);
    put32(data + 4, value >> 32);
}

static uint8_t *primary()
{
    return image.data() + sector_size;
}

static uint8_t *backup()
{
    return image.data() + image.size() - sector_size;
}

static void header_crc(uint8_t *hdr)
{
    put32(hdr + HEADER_CRC_OFFSET, 0);
    put32(hdr + HEADER_CRC_OFFSET,
          crc32(0L, hdr, GET_4_BYTES(hdr + HEADER_SIZE_OFFSET)));
}

static void name_entry(uint8_t *entry, const char *name)
{
    memset(entry + PARTITION_NAME_OFFSET, 0, MAX_GPT_NAME_SIZE);
    for (size_t i = 0; i < strlen(name); ++i)
        entry[PARTITION_NAME_OFFSET + i * 2] = name[i];
}

static uint8_t *array_for(uint8_t *hdr)
{
    return image.data() + GET_8_BYTES(hdr + PENTRIES_OFFSET) * sector_size;
}

static void array_crc(uint8_t *hdr)
{
    uint32_t size = GET_4_BYTES(hdr + PARTITION_COUNT_OFFSET) *
                    GET_4_BYTES(hdr + PENTRY_SIZE_OFFSET);
    put32(hdr + PARTITION_CRC_OFFSET, crc32(0L, array_for(hdr), size));
    header_crc(hdr);
}

static void make_image(uint32_t block = 512, uint32_t entry_size = 128,
                       uint32_t count = 128, uint32_t header_size = 92)
{
    sector_size = block;
    image.assign((size_t)block * 2048, 0);
    reset_io();
    uint64_t blocks = ((uint64_t)count * entry_size + block - 1) / block;
    uint64_t backup_entries = 2047 - blocks - 2;
    for (unsigned instance = 0; instance < 2; ++instance) {
        uint8_t *hdr = instance ? backup() : primary();
        memcpy(hdr, GPT_SIGNATURE, 8);
        put32(hdr + 8, 0x10000);
        put32(hdr + HEADER_SIZE_OFFSET, header_size);
        put64(hdr + PRIMARY_HEADER_OFFSET, instance ? 2047 : 1);
        put64(hdr + BACKUP_HEADER_OFFSET, instance ? 1 : 2047);
        put64(hdr + FIRST_USABLE_LBA_OFFSET, 3 + blocks + 3);
        put64(hdr + LAST_USABLE_LBA_OFFSET, backup_entries - 4);
        memset(hdr + 56, 0x5a, 16);
        put64(hdr + PENTRIES_OFFSET, instance ? backup_entries : 3);
        put32(hdr + PARTITION_COUNT_OFFSET, count);
        put32(hdr + PENTRY_SIZE_OFFSET, entry_size);
        uint8_t *arr = array_for(hdr);
        for (uint32_t i = 0; i < count; ++i) {
            uint8_t *entry = arr + (size_t)i * entry_size;
            memset(entry, 0x17, TYPE_GUID_SIZE);
            put64(entry + FIRST_LBA_OFFSET, 3 + blocks + 3 + i);
            put64(entry + LAST_LBA_OFFSET, 3 + blocks + 3 + i);
            name_entry(entry, i ? "boot_b" : "boot_a");
        }
        //The final entry detects traversal that assumes 128 entries or 128 bytes.
        name_entry(arr + (size_t)(count - 1) * entry_size, "last_a");
        array_crc(hdr);
    }
}

static gpt_disk *load()
{
    gpt_disk *disk = gpt_disk_alloc();
    assert(disk);
    assert(gpt_disk_get_disk_info("boot_a", disk) == 0);
    return disk;
}

static void expect_load_failure(const char *label)
{
    gpt_disk *disk = gpt_disk_alloc();
    assert(disk);
    int rc = gpt_disk_get_disk_info("boot_a", disk);
    if (rc != -1)
        fprintf(stderr, "Unexpectedly accepted %s\n", label);
    assert(rc == -1);
    assert(disk->is_initialized != GPT_DISK_INIT_MAGIC);
    assert(write_calls == 0);
    gpt_disk_free(disk);
    ++rejected_images;
}

static void test_valid()
{
    for (uint32_t block : {512U, 4096U}) {
        for (uint32_t entry_size : {128U, 136U, 256U, 384U, 512U}) {
            for (uint32_t count : {3U, 129U, 257U}) {
                make_image(block, entry_size, count, 104);
                gpt_disk *disk = load();
                assert(disk->hdr_crc == crc32(0L, disk->hdr, 104));
                assert(disk->hdr_bak_crc == crc32(0L, disk->hdr_bak, 104));
                assert(disk->pentry_arr_size == entry_size * count);
                assert(gpt_disk_get_pentry(disk, "last_a", PRIMARY_GPT) ==
                       disk->pentry_arr + (size_t)(count - 1) * entry_size);
                assert(gpt_disk_get_pentry(disk, "last_a", SECONDARY_GPT) ==
                       disk->pentry_arr_bak + (size_t)(count - 1) * entry_size);
                assert(!gpt_disk_get_pentry(disk, "missing", PRIMARY_GPT));
                assert(!gpt_disk_get_pentry(disk, "boot_a", (gpt_instance)2));
                assert(!gpt_disk_get_pentry(disk,
                       "123456789012345678901234567890123456789", PRIMARY_GPT));
                uint8_t *entry = gpt_disk_get_pentry(disk, "boot_a", PRIMARY_GPT);
                assert(entry);
                entry[AB_FLAG_OFFSET] ^= AB_PARTITION_ATTR_SLOT_ACTIVE;
                assert(gpt_disk_get_pentry(disk, "last_a", PRIMARY_GPT));
                assert(gpt_disk_commit(disk) == -1 && write_calls == 0);
                assert(gpt_disk_update_crc(disk) == 0);
                assert(gpt_disk_commit(disk) == 0);
                assert(gpt_validate_header(primary(), block, image.size(), PRIMARY_GPT) == 0);
                assert(gpt_validate_header(backup(), block, image.size(), SECONDARY_GPT) == 0);
                gpt_disk *roundtrip = load();
                assert(roundtrip->pentry_arr[AB_FLAG_OFFSET] == entry[AB_FLAG_OFFSET]);
                gpt_disk_free(roundtrip);
                gpt_disk_free(disk);
            }
        }
    }
    puts("PASS valid GPT: 30 layouts, legacy entry sizes, extended headers, all entries, roundtrip, snapshot CRC");
}

static void test_bad_headers()
{
    for (bool secondary : {false, true}) {
        auto target = [secondary]() { return secondary ? backup() : primary(); };
        for (uint32_t size : {0U, 16U, 91U, 513U, UINT32_MAX}) {
            make_image();
            put32(target() + HEADER_SIZE_OFFSET, size);
            expect_load_failure("header size");
        }
        make_image(); target()[0] ^= 1;
        expect_load_failure("signature");
        make_image(); target()[HEADER_CRC_OFFSET] ^= 1;
        expect_load_failure("header CRC");
        make_image(); array_for(target())[17] ^= 1;
        expect_load_failure("array CRC");
        for (uint32_t size : {0U, 64U, 127U, 129U, UINT32_MAX}) {
            make_image(); put32(target() + PENTRY_SIZE_OFFSET, size); header_crc(target());
            expect_load_failure("entry size");
        }
        for (uint32_t count : {0U, 0x2000001U, UINT32_MAX}) {
            make_image(); put32(target() + PARTITION_COUNT_OFFSET, count); header_crc(target());
            expect_load_failure("entry count / product overflow");
        }
        for (uint64_t offset : std::initializer_list<uint64_t>{0, 1, 2047, 2048,
                                UINT64_MAX / 512 + 1, UINT64_MAX}) {
            make_image(); put64(target() + PENTRIES_OFFSET, offset); header_crc(target());
            expect_load_failure("array range / offset overflow");
        }
        make_image(); put64(target() + PENTRIES_OFFSET, secondary ? 2000 : 39);
        header_crc(target()); expect_load_failure("array overlaps usable LBAs");
        for (unsigned field : {PRIMARY_HEADER_OFFSET, BACKUP_HEADER_OFFSET,
                               FIRST_USABLE_LBA_OFFSET, LAST_USABLE_LBA_OFFSET}) {
            make_image(); put64(target() + field, UINT64_MAX); header_crc(target());
            expect_load_failure("header LBA range");
        }
    }
    make_image(); put32(backup() + HEADER_SIZE_OFFSET, 104); header_crc(backup());
    expect_load_failure("primary/backup header size mismatch");
    make_image(); put32(backup() + PARTITION_COUNT_OFFSET, 64); header_crc(backup());
    expect_load_failure("primary/backup array size mismatch");
    make_image(); put32(backup() + PENTRY_SIZE_OFFSET, 256);
    put32(backup() + PARTITION_COUNT_OFFSET, 64); header_crc(backup());
    expect_load_failure("primary/backup equal bytes but different stride/count");
    make_image(); backup()[56] ^= 1; header_crc(backup());
    expect_load_failure("disk GUID mismatch");
    make_image(); put64(backup() + LAST_USABLE_LBA_OFFSET, 2007); header_crc(backup());
    expect_load_failure("usable range mismatch");
    make_image(); put32(backup() + 8, 0x10001); header_crc(backup());
    expect_load_failure("revision mismatch");
    make_image(); image.pop_back(); expect_load_failure("unaligned disk length");
    make_image(); sector_size = 0; expect_load_failure("zero block size");
    make_image(); sector_size = 64; expect_load_failure("undersized block");
    make_image(); image.resize(512); expect_load_failure("undersized disk");
    printf("PASS %u corrupt GPT/header/array/geometry rejection cases\n", rejected_images);
}

static void test_cached_validation()
{
    for (unsigned change = 0; change < 8; ++change) {
        make_image();
        gpt_disk *disk = load();
        switch (change) {
        case 0: put32(disk->hdr + HEADER_SIZE_OFFSET, UINT32_MAX); break;
        case 1: put32(disk->hdr_bak + PENTRY_SIZE_OFFSET, 0); break;
        case 2: put32(disk->hdr + PARTITION_COUNT_OFFSET, UINT32_MAX); break;
        case 3: put64(disk->hdr_bak + PENTRIES_OFFSET, UINT64_MAX); break;
        case 4: disk->pentry_arr_size -= 1; break;
        case 5: disk->pentry_size = 0; break;
        case 6: put32(disk->hdr_bak + HEADER_SIZE_OFFSET, 104); break;
        case 7: disk->hdr[0] = 0; break;
        }
        assert(!gpt_disk_get_pentry(disk, "boot_a", PRIMARY_GPT));
        assert(gpt_disk_update_crc(disk) == -1);
        assert(gpt_disk_commit(disk) == -1);
        assert(!write_calls);
        gpt_disk_free(disk);
    }
    make_image();
    gpt_disk *disk = load();
    image.resize(image.size() - sector_size);
    assert(gpt_disk_commit(disk) == -1 && !write_calls);
    gpt_disk_free(disk);
    make_image(); disk = load(); sector_size = 4096;
    assert(gpt_disk_commit(disk) == -1 && !write_calls);
    gpt_disk_free(disk);
    puts("PASS cached metadata and commit geometry validation before writes");
}

static void test_io()
{
    make_image();
    uint8_t buffer[512];
    chunk_size = 7; read_interrupts = 2; seek_interrupts = 1;
    assert(blk_rw(fake_fd, 0, 512, buffer, sizeof(buffer)) == 0);
    assert(!memcmp(buffer, primary(), sizeof(buffer)));
    write_interrupts = 2; sync_interrupts = 2;
    assert(blk_rw(fake_fd, 1, 512, buffer, sizeof(buffer)) == 0);
    assert(write_calls > 2 && sync_calls == 3);
    reset_io(); read_limit = 17;
    assert(blk_rw(fake_fd, 0, 512, buffer, sizeof(buffer)) == -1 && errno == EIO);
    reset_io(); read_limit = 0;
    assert(blk_rw(fake_fd, 0, 512, buffer, sizeof(buffer)) == -1 && errno == EIO);
    reset_io(); zero_write = true;
    assert(blk_rw(fake_fd, 1, 512, buffer, sizeof(buffer)) == -1 && errno == EIO);
    assert(!sync_calls);
    reset_io(); read_error = true;
    assert(blk_rw(fake_fd, 0, 512, buffer, sizeof(buffer)) == -1);
    reset_io(); write_error = true;
    assert(blk_rw(fake_fd, 1, 512, buffer, sizeof(buffer)) == -1);
    reset_io(); sync_error = true;
    assert(blk_rw(fake_fd, 1, 512, buffer, sizeof(buffer)) == -1);
    reset_io(); seek_error = true;
    assert(blk_rw(fake_fd, 0, 512, buffer, sizeof(buffer)) == -1);
    reset_io();
    assert(blk_rw(fake_fd, 0, -1, buffer, sizeof(buffer)) == -1);
    assert(blk_rw(fake_fd, 0, INT64_MAX - 8, buffer, sizeof(buffer)) == -1);
    assert(blk_rw(fake_fd, 0, 0, NULL, sizeof(buffer)) == -1);
    make_image(); chunk_size = 11;
    gpt_disk *disk = load();
    write_interrupts = 1; sync_interrupts = 1;
    assert(gpt_disk_update_crc(disk) == 0);
    assert(gpt_disk_commit(disk) == 0);
    gpt_disk_free(disk);
    make_image(); read_limit = 100;
    expect_load_failure("short header EOF");
    make_image(); read_limit = 2 * sector_size + 100;
    expect_load_failure("short array EOF");
    make_image(); disk = load(); zero_write = true;
    assert(gpt_disk_commit(disk) == -1);
    gpt_disk_free(disk);
    make_image(); disk = load(); sync_fail_on_call = 5;
    assert(gpt_disk_commit(disk) == -1 && sync_calls == 5);
    gpt_disk_free(disk);
    puts("PASS short I/O, EINTR, EOF, zero progress, errors, bounds, public API I/O, final sync");
}

static void test_update_stages()
{
    make_image();
    for (uint8_t *hdr : {primary(), backup()}) {
        uint8_t *arr = array_for(hdr);
        name_entry(arr, "abl");
        name_entry(arr + 128, "ablbak");
        array_crc(hdr);
    }
    std::vector<uint8_t> original = image;
    chunk_size = 13;
    assert(prepare_partitions(UPDATE_MAIN, "/dev/block/mmcblk0") == 0);
    assert(primary()[0] == 0);
    assert(!memcmp(backup(), GPT_SIGNATURE, 8));
    assert(prepare_partitions(UPDATE_BACKUP, "/dev/block/mmcblk0") == 0);
    assert(backup()[0] == 0);
    assert(!memcmp(primary(), GPT_SIGNATURE, 8));
    assert(prepare_partitions(UPDATE_FINALIZE, "/dev/block/mmcblk0") == 0);
    assert(image == original);
    make_image(); put32(primary() + HEADER_SIZE_OFFSET, UINT32_MAX);
    enum gpt_state state;
    assert(gpt_get_state(fake_fd, PRIMARY_GPT, &state) == 0 && state == GPT_BAD_CRC);
    assert(gpt_set_state(fake_fd, PRIMARY_GPT, GPT_OK) == -1);
    assert(gpt2_set_boot_chain(fake_fd, NORMAL_BOOT) == -1 && !write_calls);
    make_image(); put32(backup() + PARTITION_COUNT_OFFSET, 64); header_crc(backup());
    assert(gpt2_set_boot_chain(fake_fd, NORMAL_BOOT) == -1 && !write_calls);
    puts("PASS existing staged boot update and malformed legacy paths");
}

int main()
{
    test_valid();
    test_bad_headers();
    test_cached_validation();
    test_io();
    test_update_stages();
    puts("PASS all GPT regression tests (synthetic memory I/O only)");
}
