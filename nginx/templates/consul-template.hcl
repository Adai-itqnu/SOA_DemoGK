template {
  source      = "/templates/api-gateway.ctmpl"
  destination = "/etc/nginx/conf.d/api-gateway.conf"
  perms       = 0644
  command     = "nginx -s reload || nginx -g 'daemon off;'"
}


