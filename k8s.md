## Kubernetes

Kubernetes, also known as K8s, is an open-source system for automating deployment, scaling, and management of
containerized applications

# Complete deployment guide for k8s deloyment

* contains every functionality
* compatible with amd64, arm64 and armv7l

## First. Get all file in k8s folder

Download `k8s` file to a directory on your k8s server and go to this folder

## 1. Create Redis deloyment

```shell
kubectl apply -f 01.redis.yml
```

This command will create ytdl namespace, redis pod and redis service

## 2. Creat MariaDB deloyment

```shell
kubectl apply -f 02.mariadb.yml
```

This deloyment will claim 10GB storage from storageClassName: longhorn. Please replace longhorn with your
storageClassName before apply.

## 3. Set environment variables

Create configMap for env

### 3.1 Edit configmap.yml

```shell
vim 03.configmap.yml
```

you can configure all the following environment variables:

* PYRO_WORKERS: number of workers for pyrogram, default is 100
* WORKERS: workers count for celery
* APP_ID: **REQUIRED**, get it from https://core.telegram.org/
* APP_HASH: **REQUIRED**
* TOKEN: **REQUIRED**
* REDIS: **REQUIRED if you need VIP mode and cache** ⚠️ Don't publish your redis server on the internet. ⚠️

* OWNER: owner username
* QUOTA: quota in bytes
* EX: quota expire time
* MULTIPLY: vip quota comparing to normal quota
* USD2CNY: exchange rate
* VIP: VIP mode, default: disable
* AFD_LINK
* COFFEE_LINK
* COFFEE_TOKEN
* AFD_TOKEN
* AFD_USER_ID

* AUTHORIZED_USER: users that could use this bot, user_id, separated with `,`
* REQUIRED_MEMBERSHIP: group or channel username, user must join this group to use the bot. Could be use with
  above `AUTHORIZED_USER`

* ENABLE_CELERY: Distribution mode, default: disable. You'll can setup workers in different locations.
* ENABLE_FFMPEG: enable ffmpeg so Telegram can stream
* MYSQL_HOST: you'll have to setup MySQL if you enable VIP mode
* MYSQL_USER
* MYSQL_PASS
* GOOGLE_API_KEY: YouTube API key, required for YouTube video subscription.
* AUDIO_FORMAT: audio format, default is m4a. You can set to any known and supported format for ffmpeg. For
  example,`mp3`, `flac`, etc. ⚠️ m4a is the fastest. Other formats may affect performance.
* ARCHIVE_ID: group or channel id/username. All downloads will send to this group first and then forward to end user.
  **Inline button will be lost during the forwarding.**

### 3.2 Apply configMap for environment variables

```shell
kubectl apply -f 03.configmap.yml
```

## 4. Run Master Celery

```shell
kubectl apply -f 04.ytdl-master.yml
```

This deloyment will create ytdl-pvc PersistentVolumeClaim on storageClassName: longhorn. This clain will contain vnstat,
cookies folder and flower database. Please replace longhorn with your storageClassName before apply

### 4.1 Setup instagram cookies

Required if you want to support instagram.

You can use this extension
[Get cookies.txt](https://chrome.google.com/webstore/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid)
to get instagram cookies

Get pod running ytdl master:

```shell
kubectl get pods --namespace ytdl
```

Name should be ytdl-xxxxxxxx

Access to pod

```shell
kubectl --namespace=ytdl exec --stdin --tty ytdl-xxx -- sh
```

(replace ytdl-xxx by your pod name)

Go to ytdl-pvc mounted folder

```shell
cd /ytdlbot/ytdlbot/data/
vim  instagram.com_cookies.txt
# paste your cookies
```

## 5. Run Worker Celery

```shell
kubectl apply -f 05.ytdl-worker.yml
```

## 6. Run Flower image (OPTIONAL)

### 6.1 Setup flower db

Get pod running ytdl master:

```shell
kubectl get pods --namespace ytdl
```

Name should be ytdl-xxxxxxxx

Access to pod

```shell
kubectl --namespace=ytdl exec --stdin --tty ytdl-xxx -- sh
```

(replace ytdl-xxx by your pod name)

Go to ytdl-pvc mounted folder

```shel
cd /var/lib/vnstat/
```

Create flower database file

```shell
{} ~ python3
Python 3.9.9 (main, Nov 21 2021, 03:22:47)
[Clang 12.0.0 (clang-1200.0.32.29)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> import dbm;dbm.open("flower","n");exit()
```

### 6.2 Config Flower Ingress

This step need config ingress from line 51 of file 06.flower.yml with your ingress service. Need for access from
internet.
YML file should be adjusted depending on your load balancing, ingress and network system

For active SSL

```yml
cert-manager.io/cluster-issuer: letsencrypt-prod
```

Replace nginx by your ingress service

```yml
ingressClassName: nginx
```

Add your domain, example

```yml
tls:
  - hosts:
      - flower.benny.com
    secretName: flower-tls
  rules:
    - host: flower.benny.com
```

### 6.3 Apply Flower deloyment

```shell
kubectl apply -f 06.flower.yml
```
