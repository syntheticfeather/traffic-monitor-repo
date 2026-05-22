#include "hash.h"

// 全局变量定义
node sentinel_pool[HASH_SIZE];
node flow_node_pool[MAX_FLOWS];
node *hash_table[HASH_SIZE];
int cur_flow = 0;
pthread_mutex_t pool_mutex = PTHREAD_MUTEX_INITIALIZER;

int flow_hash(unsigned int s_ip, unsigned int d_ip,
              unsigned short s_port, unsigned short d_port)
{
    unsigned long long h = ((unsigned long long)s_ip << 32) | d_ip;
    h ^= ((unsigned long long)s_port << 16) | d_port;
    return h % HASH_SIZE;
}

void init()
{
    for (int i = 0; i < HASH_SIZE; i++) {
        sentinel_pool[i].next = NULL;
        hash_table[i] = &sentinel_pool[i];
    }
    cur_flow = 0;
}

node *find_flow(unsigned int s_ip, unsigned int d_ip,
                unsigned short s_port, unsigned short d_port)
{
    int key = flow_hash(s_ip, d_ip, s_port, d_port);
    node *pnode = hash_table[key]->next;
    while (pnode != NULL
           && !(pnode->src_ip == s_ip && pnode->dst_ip == d_ip
                && pnode->src_port == s_port && pnode->dst_port == d_port)) {
        pnode = pnode->next;
    }
    return pnode;
}

node *create_flow(unsigned int s_ip, unsigned int d_ip,
                  unsigned short s_port, unsigned short d_port)
{
    if (cur_flow >= MAX_FLOWS) {
        delete_flow();
    }

    int key = flow_hash(s_ip, d_ip, s_port, d_port);
    node *pnode = &flow_node_pool[(cur_flow % MAX_FLOWS)];

    pnode->src_ip = s_ip;
    pnode->dst_ip = d_ip;
    pnode->src_port = s_port;
    pnode->dst_port = d_port;
    pnode->total_bytes = 0;
    pnode->max_rate = 0;
    pnode->last_bytes = 0;
    pnode->last_bytes_10s = 0;
    pnode->last_bytes_40s = 0;
    pnode->first_seen = time(NULL);

    node *sentinel = hash_table[key];
    pnode->next = sentinel->next;
    sentinel->next = pnode;

    cur_flow++;
    return pnode;
}

void delete_flow()
{
    node *old = &flow_node_pool[cur_flow % MAX_FLOWS];
    unsigned int s_ip = old->src_ip;
    unsigned int d_ip = old->dst_ip;
    unsigned short s_port = old->src_port;
    unsigned short d_port = old->dst_port;
    int key = flow_hash(s_ip, d_ip, s_port, d_port);

    node *prev = hash_table[key];
    node *cur = prev->next;
    while (cur != NULL
           && !(cur->src_ip == s_ip && cur->dst_ip == d_ip
                && cur->src_port == s_port && cur->dst_port == d_port)) {
        prev = cur;
        cur = cur->next;
    }
    if (cur != NULL) {
        prev->next = cur->next;
    }
}
