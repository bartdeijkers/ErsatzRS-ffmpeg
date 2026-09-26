#!/usr/bin/env python3
"""Exercise the actual FFmpeg readrate function with a deterministic clock.

Usage: python3 scripts/verify-readrate-source.py SOURCE/fftools/ffmpeg_demux.c
Requires a C compiler (cc). Unpatched n9.0 must fail its two continuous cases.
"""
from pathlib import Path
import subprocess, sys, tempfile

source = Path(sys.argv[1]).read_text()
function = source[
    source.index("static void readrate_sleep(") : source.index(
        "\nstatic int do_send(", source.index("static void readrate_sleep(")
    )
]
pre = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define AV_TIME_BASE 1000000
#define AV_NOPTS_VALUE INT64_MIN
#define AVMEDIA_TYPE_VIDEO 0
#define AVMEDIA_TYPE_AUDIO 1
#define AVMEDIA_TYPE_SUBTITLE 3
#define AV_LOG_WARNING 0
#define AV_LOG_DEBUG 0
#define FFMAX(a,b) ((a)>(b)?(a):(b))
typedef struct { int codec_type; } Parameters;
typedef struct { Parameters *par; void *priv; } InputStream;
typedef struct { int discard,finished; int64_t first_dts,dts; } DemuxStream;
typedef struct { int64_t start_time_effective,start_time; int nb_streams; InputStream **streams; } InputFile;
typedef struct { InputFile f; double readrate_initial_burst,readrate,readrate_catchup; int64_t wallclock_start,lag,resume_wc,resume_progress; } Demuxer;
static int copy_ts=0,start_at_zero=0;
static int64_t slept,now=1000000;
static DemuxStream *ds_from_ist(InputStream *i){return i->priv;}
static int64_t av_rescale(int64_t a,int64_t b,int64_t c){return a*b/c;}
static int64_t av_gettime_relative(void){return now;}
static void av_usleep(int64_t us){slept+=us;}
#define av_log_once(...) ((void)resume_warn, (void)pts)
"""
post = r"""
static int failures;
static void check(const char *name, const int *types, DemuxStream *states, int count, int64_t expected){
 Parameters p[3]; InputStream in[3]; InputStream *ptrs[3];
 for(int i=0;i<count;i++){p[i].codec_type=types[i];in[i]=(InputStream){&p[i],&states[i]};ptrs[i]=&in[i];}
 Demuxer d={.f={.nb_streams=count,.streams=ptrs},.readrate=1,.readrate_catchup=1,.wallclock_start=now};
 slept=0;readrate_sleep(&d);
 printf("%s: sleep=%lld expected=%lld\n",name,(long long)slept,(long long)expected);
 failures+=slept!=expected;
}
int main(void){
 check("audio advances while subtitle frozen",(int[]){1,3},(DemuxStream[]){{.dts=500000},{.dts=0}},2,500000);
 check("slowest audio/video wins",(int[]){0,1,3},(DemuxStream[]){{.dts=800000},{.dts=400000},{.dts=0}},3,400000);
 check("sparse-only fallback",(int[]){3,3},(DemuxStream[]){{.dts=700000},{.dts=900000}},2,700000);
 check("finished audio excluded",(int[]){1,3},(DemuxStream[]){{.dts=100000,.finished=1},{.dts=700000}},2,700000);
 check("discarded audio excluded",(int[]){1,3},(DemuxStream[]){{.dts=100000,.discard=1},{.dts=700000}},2,700000);
 check("unstarted audio excluded",(int[]){1,3},(DemuxStream[]){{.first_dts=AV_NOPTS_VALUE},{.dts=700000}},2,700000);
 check("no active stream",(int[]){1},(DemuxStream[]){{.finished=1}},1,0);
 return failures ? EXIT_FAILURE : EXIT_SUCCESS;
}
"""
with tempfile.TemporaryDirectory() as td:
    c = Path(td) / "pacing.c"
    binary = Path(td) / "pacing"
    c.write_text(pre + function + post)
    subprocess.run(
        ["cc", "-Wall", "-Wextra", "-Werror", "-o", str(binary), str(c)], check=True
    )
    sys.exit(subprocess.run([str(binary)]).returncode)
