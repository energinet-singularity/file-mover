FROM alpine:3.14.2

RUN apk add --no-cache --upgrade --update bash cifs-utils

#Include bash-script and make it executable
COPY filemover.sh /
RUN chmod +x /filemover.sh

CMD ["./filemover.sh"]