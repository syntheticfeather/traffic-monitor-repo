#include "hash.h"
#include <pcap.h>
#include <netinet/ip.h>
#include <netinet/in.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/file.h>
#include <arpa/inet.h>

#define STATS_FILE "/mnt/p0/traffic_monitor/stats.txt"

/* ── 回调：每抓到一个包就调一次 ── */
void packet_handler(unsigned char *user, const struct pcap_pkthdr *hdr,
                    const unsigned char *bytes)
{
    struct ip *iph = (struct ip *)(bytes + 14);
    unsigned int src_ip = iph->ip_src.s_addr;
    unsigned int dst_ip = iph->ip_dst.s_addr;
    unsigned int pkt_len = ntohs(iph->ip_len);
    unsigned short src_port = 0, dst_port = 0;

    if (iph->ip_p == IPPROTO_TCP || iph->ip_p == IPPROTO_UDP) {
        unsigned int ip_hdr_len = iph->ip_hl * 4;
        unsigned short *ports = (unsigned short *)(bytes + 14 + ip_hdr_len);
        src_port = ntohs(ports[0]);
        dst_port = ntohs(ports[1]);
    }

    pthread_mutex_lock(&pool_mutex);
    {
        node *flow = find_flow(src_ip, dst_ip, src_port, dst_port);
        if (flow == NULL) {
            flow = create_flow(src_ip, dst_ip, src_port, dst_port);
        }
        flow->total_bytes += pkt_len;
    }
    pthread_mutex_unlock(&pool_mutex);
}

/* ── 抓包线程 ── */
void *capture_thread(void *arg)
{
    char errbuf[PCAP_ERRBUF_SIZE];
    pcap_t *handle = pcap_open_live("eth0", 65535, 1, 1000, errbuf);
    if (!handle) {
        fprintf(stderr, "pcap_open_live: %s\n", errbuf);
        return NULL;
    }

    struct bpf_program fp;
    if (pcap_compile(handle, &fp, "ip", 0, 0) == 0) {
        pcap_setfilter(handle, &fp);
    }

    pcap_loop(handle, 0, packet_handler, NULL);
    pcap_close(handle);
    return NULL;
}

/* ── 统计线程（每 2 秒写一次文件）── */
void *stats_thread(void *arg)
{
    // 快照缓冲区
    struct {
        unsigned int src_ip, dst_ip;
        unsigned short src_port, dst_port;
        unsigned long long total, rate_2s, rate_10s, rate_40s, max;
    } snap[MAX_FLOWS] = {0};
    int snap_count = 0, cycle = 0;

    while (1) {
        sleep(2);
        cycle++;

        pthread_mutex_lock(&pool_mutex);
        {
            int total = cur_flow < MAX_FLOWS ? cur_flow : MAX_FLOWS;
            snap_count = total;
            for (int i = 0; i < total; i++) {
                node *e = &flow_node_pool[i];
                snap[i].src_ip   = e->src_ip;
                snap[i].dst_ip   = e->dst_ip;
                snap[i].src_port = e->src_port;
                snap[i].dst_port = e->dst_port;
                snap[i].total    = e->total_bytes;

                unsigned long long rate_2s = (e->total_bytes - e->last_bytes) / 2;
                if (rate_2s > e->max_rate) e->max_rate = rate_2s;
                snap[i].rate_2s = rate_2s;
                snap[i].max     = e->max_rate;
                e->last_bytes = e->total_bytes;

                // 每 10s 算一次
                snap[i].rate_10s = (cycle % 5 == 0)
                    ? (e->total_bytes - e->last_bytes_10s) / 10
                    : snap[i].rate_10s;
                if (cycle % 5 == 0) e->last_bytes_10s = e->total_bytes;

                // 每 40s 算一次
                snap[i].rate_40s = (cycle % 20 == 0)
                    ? (e->total_bytes - e->last_bytes_40s) / 40
                    : snap[i].rate_40s;
                if (cycle % 20 == 0) e->last_bytes_40s = e->total_bytes;
            }
        }
        pthread_mutex_unlock(&pool_mutex);

        // 写文件
        FILE *f = fopen(STATS_FILE, "w");
        if (!f) continue;
        flock(fileno(f), LOCK_EX);
        for (int i = 0; i < snap_count; i++) {
            char s[INET_ADDRSTRLEN], d[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &snap[i].src_ip, s, sizeof(s));
            inet_ntop(AF_INET, &snap[i].dst_ip, d, sizeof(d));
            fprintf(f, "%s:%u -> %s:%u | total:%llu | 2s:%llu B/s | 10s:%llu B/s | 40s:%llu B/s | max:%llu B/s\n",
                    s, snap[i].src_port, d, snap[i].dst_port,
                    snap[i].total, snap[i].rate_2s,
                    snap[i].rate_10s, snap[i].rate_40s, snap[i].max);
        }
        flock(fileno(f), LOCK_UN);
        fclose(f);
    }
    return NULL;
}

int main()
{
    init();

    pthread_t cap_tid, stats_tid;
    pthread_create(&cap_tid, NULL, capture_thread, NULL);
    pthread_create(&stats_tid, NULL, stats_thread, NULL);

    pthread_join(cap_tid, NULL);
    pthread_join(stats_tid, NULL);
    return 0;
}
