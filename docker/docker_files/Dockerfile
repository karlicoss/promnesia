FROM python:3

RUN mkdir /user_data && \
    mkdir /usr/src/promnesia

WORKDIR /usr/src/promnesia
COPY . .

ARG VERSION=0
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_PROMNESIA=${VERSION}  pip install --no-cache-dir -e .[all]

ENV PPATH=/usr/src/promnesia:${PPATH}
VOLUME /user_data

EXPOSE 13131
CMD ["python", "-m", "promnesia", "serve", "--db", "/user_data/promnesia.sqlite", "--port", "13131"]
