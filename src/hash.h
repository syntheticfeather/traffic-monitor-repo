#ifndef HASH_H
#define HASH_H

#include <time.h>
#include <pthread.h>

#define HASH_SIZE 1999    // 哈希表槽数（质数）
#define MAX_FLOWS 2000    // 流结点池大小

typedef struct node {
    unsigned int src_ip;
    unsigned int dst_ip;
    unsigned short src_port;
    unsigned short dst_port;
    unsigned long long total_bytes;
    unsigned long long max_rate;
    unsigned long long last_bytes;       // 2s 快照
    unsigned long long last_bytes_10s;   // 10s 快照
    unsigned long long last_bytes_40s;   // 40s 快照
    time_t first_seen;
    struct node *next;
} node;

// 全局变量（在 hash.c 中定义）
extern node sentinel_pool[HASH_SIZE];
extern node flow_node_pool[MAX_FLOWS];
extern node *hash_table[HASH_SIZE];
extern int cur_flow;
extern pthread_mutex_t pool_mutex;       // 保护流结点池

// 函数声明
void init(void);
int  flow_hash(unsigned int s_ip, unsigned int d_ip,
               unsigned short s_port, unsigned short d_port);
node *find_flow(unsigned int s_ip, unsigned int d_ip,
                unsigned short s_port, unsigned short d_port);
node *create_flow(unsigned int s_ip, unsigned int d_ip,
                  unsigned short s_port, unsigned short d_port);
void delete_flow(void);

#endif
