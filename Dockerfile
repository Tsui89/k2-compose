FROM python:2.7-alpine
ARG branch
ARG commit
ARG buildtime
ARG owner
LABEL branch=$branch \
        commit=$commit \
        buildtime=$buildtime \
        owner=$owner
COPY README.rst /docs/
# put your commands here
RUN pip install k2-compose==$version -i http://pypi.douban.com/simple --trusted-host pypi.douban.com
ENTRYPOINT ["ping", "localhost"]
