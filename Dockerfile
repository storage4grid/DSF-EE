FROM python:3.6-slim

COPY . /srv/economic_app
WORKDIR /srv/economic_app

RUN apt-get clean \
    && apt-get -y update

RUN apt-get -y install nginx \
    && apt-get -y install python3-dev \
    && apt-get -y install build-essential

RUN pip3 install -r requirements.txt --src /usr/local/src


# -------------------------------------------------------------- #
# Exploit Let's encrypt certificates stored on dedicated volumes
# -------------------------------------------------------------- #
# Build up dedicated volumes for
# Logs:
RUN mkdir /var/log/letsencrypt 
VOLUME /var/log/letsencrypt 
# Certificates:
RUN mkdir /etc/letsencrypt
VOLUME /etc/letsencrypt
# Lib:
RUN mkdir /var/lib/letsencrypt
VOLUME /var/lib/letsencrypt

# -------------------------------------------------------------- #
# Exploit self-signed certificates (previously built)
# -------------------------------------------------------------- #
# RUN openssl req -x509 -nodes -days 565 -newkey rsa:2048 -keyout /etc/ssl/private/nginx-selfsigned.key -out /etc/ssl/certs/nginx-selfsigned.crt
# RUN openssl dhparam -dsaparam -out /etc/ssl/certs/dhparam.pem 4096
#COPY ssl/nginx-selfsigned.key /etc/ssl/private/nginx-selfsigned.key
#COPY ssl/nginx-selfsigned.crt /etc/ssl/certs/nginx-selfsigned.crt
#COPY ssl/dhparam.pem /etc/ssl/certs/dhparam.pem
##

COPY nginx.conf /etc/nginx
COPY economicserver-nginx /etc/nginx/sites-available/economicserver
RUN  ln -s /etc/nginx/sites-available/economicserver /etc/nginx/sites-enabled/

RUN chmod +x ./start.sh

CMD ["./start.sh"]
