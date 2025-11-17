FROM nginx:1.27-alpine

RUN apk add --no-cache curl wget unzip

ENV CONSUL_TEMPLATE_VERSION=0.39.0

RUN wget https://releases.hashicorp.com/consul-template/${CONSUL_TEMPLATE_VERSION}/consul-template_${CONSUL_TEMPLATE_VERSION}_linux_amd64.zip \
    && unzip consul-template_${CONSUL_TEMPLATE_VERSION}_linux_amd64.zip \
    && mv consul-template /usr/local/bin/consul-template \
    && rm consul-template_${CONSUL_TEMPLATE_VERSION}_linux_amd64.zip

COPY nginx.conf /etc/nginx/nginx.conf
COPY templates /templates

CMD ["sh", "-c", "consul-template -config=/templates/consul-template.hcl & nginx -g 'daemon off;'"]


