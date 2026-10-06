/* Test the actual built WebP demuxer without decoding or application bindings.
 *
 * Build against the exact configured FFmpeg source and its static prefix:
 * cc -I<ffmpeg-source> $(pkg-config --cflags libavformat libavcodec libavutil) \
 *   scripts/verify-webp-metadata.c -o verify-webp-metadata \
 *   $(pkg-config --libs --static libavformat libavcodec libavutil)
 *
 * verify-webp.py supplies synthetic full/truncated ICCP and EXIF fixtures.
 * Failed avformat_open_input frees its context, hiding ICCP cleanup. Calling
 * the built demuxer's header callback directly keeps that state observable.
 */
#include <stdio.h>
#include <stdlib.h>
#include "libavformat/avformat.h"
#include "libavformat/demux.h"
#include "libavutil/error.h"
#include "libavutil/mem.h"
#include "libavutil/opt.h"

static int check_iccp(const char *path, int truncated)
{
    AVFormatContext *ctx = avformat_alloc_context();
    int status = 1;
    if (!ctx)
        return 1;
    ctx->iformat = av_find_input_format("webp_anim");
    if (!ctx->iformat)
        goto done;
    const FFInputFormat *format = ffifmt(ctx->iformat);
    ctx->priv_data = av_mallocz(format->priv_data_size);
    if (!ctx->priv_data)
        goto done;
    if (ctx->iformat->priv_class) {
        *(const AVClass **)ctx->priv_data = ctx->iformat->priv_class;
        av_opt_set_defaults(ctx->priv_data);
    }
    if (avio_open(&ctx->pb, path, AVIO_FLAG_READ) < 0)
        goto done;
    const int ret = format->read_header(ctx);
    if (ctx->nb_streams != 1)
        goto done;
    const AVCodecParameters *codec = ctx->streams[0]->codecpar;
    const AVPacketSideData *side = av_packet_side_data_get(
        codec->coded_side_data, codec->nb_coded_side_data,
        AV_PKT_DATA_ICC_PROFILE);
    if (truncated) {
        if (ret >= 0 || side || codec->nb_coded_side_data != 0) {
            fprintf(stderr, "short ICCP was retained or accepted\n");
            goto done;
        }
    } else if (ret || !side || side->size != 128 ||
               side->data[36] != 'a' || side->data[37] != 'c' ||
               side->data[38] != 's' || side->data[39] != 'p') {
        fprintf(stderr, "full ICCP payload was changed or rejected\n");
        goto done;
    }
    status = 0;
done:
    avformat_close_input(&ctx);
    return status;
}

static int check_exif(const char *path, int truncated)
{
    AVFormatContext *ctx = NULL;
    AVPacket *packet = av_packet_alloc();
    int status = 1;
    if (!packet || avformat_open_input(&ctx, path, NULL, NULL) < 0)
        goto done;
    int frames = 0;
    int ret;
    while ((ret = av_read_frame(ctx, packet)) >= 0) {
        ++frames;
        av_packet_unref(packet);
        if (frames > 4) {
            fprintf(stderr, "unexpected extra packet during metadata test\n");
            goto done;
        }
    }
    if (frames != 4 || ctx->nb_streams != 1)
        goto done;
    const AVCodecParameters *codec = ctx->streams[0]->codecpar;
    const AVPacketSideData *side = av_packet_side_data_get(
        codec->coded_side_data, codec->nb_coded_side_data,
        AV_PKT_DATA_EXIF);
    if (truncated) {
        if (ret >= 0 || side || codec->nb_coded_side_data != 0) {
            fprintf(stderr, "short EXIF was retained or accepted\n");
            goto done;
        }
    } else if (ret != AVERROR_EOF || !side || side->size != 16 ||
               side->data[0] != 'I' || side->data[1] != 'I' ||
               side->data[2] != 0x2a) {
        fprintf(stderr, "full EXIF payload was changed or rejected\n");
        goto done;
    }
    status = 0;
done:
    av_packet_free(&packet);
    avformat_close_input(&ctx);
    return status;
}

int main(int argc, char **argv)
{
    if (argc != 5) {
        fprintf(stderr, "usage: verify-webp-metadata valid-iccp truncated-iccp valid-exif truncated-exif\n");
        return 2;
    }
    if (check_iccp(argv[1], 0) || check_iccp(argv[2], 1) ||
        check_exif(argv[3], 0) || check_exif(argv[4], 1))
        return 1;
    puts("Actual built WebP demuxer: full ICC/EXIF retained; short reads removed");
    return 0;
}
