/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <sys/stat.h>
#include "erofs/config.h"
#include "erofs/io.h"
#include "erofs/internal.h"
#include "erofs/dir.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int print_dirent(struct erofs_dir_context *ctx) {
    if (!ctx->dot_dotdot) printf("%u\t%.*s\n", ctx->de_ftype, ctx->de_namelen, ctx->dname);
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 5) { fprintf(stderr,"Usage: erofs_read IMAGE OFFSET cat|ls PATH\n"); return 2; }
    erofs_init_configure();
    g_sbi.bdev.offset = strtoull(argv[2], NULL, 10);
    int ret = erofs_dev_open(&g_sbi, argv[1], O_RDONLY);
    if (!ret) ret = erofs_read_superblock(&g_sbi);
    struct erofs_inode inode = {.sbi = &g_sbi};
    if (!ret) ret = erofs_ilookup(argv[4], &inode);
    if (ret) { fprintf(stderr,"Read error %d: %s\n",ret,argv[4]); return 1; }
    if (!strcmp(argv[3],"ls")) {
        struct erofs_dir_context ctx = {.dir=&inode,.cb=print_dirent};
        ret = erofs_iterate_dir(&ctx, false);
    } else if (!strcmp(argv[3],"cat")) {
        char buf[65536];
        for (uint64_t off=0; off<inode.i_size; ) {
            size_t len=inode.i_size-off > sizeof(buf) ? sizeof(buf) : inode.i_size-off;
            ret=erofs_pread(&inode,buf,len,off);
            if (ret) break;
            if (fwrite(buf,1,len,stdout)!=len) {ret=-1;break;}
            off+=len;
        }
    } else ret=-1;
    erofs_put_super(&g_sbi); erofs_dev_close(&g_sbi);
    return ret ? 1 : 0;
}
