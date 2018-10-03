#ifndef PUBLISH_H
#define PUBLISH_H

#define MAX_URL_LEN 2048

extern char url[MAX_URL_LEN];
void publish_init(void);
void publish_push(void);

void publish_value(const char *key,float value,int prec);

#endif 
