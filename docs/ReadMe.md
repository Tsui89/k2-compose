
#### 最新版本0.0.9rc6

#### 简介
k2-compose集成了docker-compose==1.14.0的基础功能，包括

	up、stop、start、restart、rm、logs、pull

优化增加了以下功能

	inspect、ps、bash、show、save

配置文件支持docker-compose原生、k2-compose定制化，这两种配置文件格式。

安装：

pip install k2-compose

最新版本： sudo pip install k2-compose==0.0.9rc6 -i pypi.douban.com/simple

项目地址：[https://github.com/Tsui89/k2-compose](https://github.com/Tsui89/k2-compose)

#### 特点
相对于docker-compose，另外还支持：

	1. 主机列表
	2. 容器列表
	3. 容器指定运行主机
	4. 容器依赖关系
	5. 容器健康检查
	6. 容器镜像的信息检测

#### k2-compose文件示例
```yaml
version: "2"
hosts:
  as: localhost:4243


project: k2-compose-test
s_extra_hosts:
  busybox: 192.168.1.2

services:

  busybox1:
    image: busybox:latest
    health_check:
      shell: echo "ok." && exit 0
      timeout: 10
    entrypoint: ["ping", "localhost"]

  busybox2:
    image: busybox:latest
    host: as
    health_check:
      http: www.baidu.com
      timeout: 10
    entrypoint: ["ping", "localhost"]
    s_depends_on:
      - busybox1
```
上述例子中hosts、project、s_extra_host、host、health_check、s_depends_on是k2-compose专有字段，

| 字段 | 描述 | 类型 | required |缺省默认值|
|:---|:---|:----|:---|:---|
|hosts|主机列表|object|false|"local":"127.0.0.1:4243"
|project|项目名称|string|false|"k2-compose"
|s_extra_hosts|域名映射表，bridge网络模式使用|object|false|空
|services.service.host|容器运行主机名，必须在hosts里定义|string|false|local
|services.service.s\_depends\_on|依赖的容器列表|array|false|空|
|services.service.health\_check|健康检查命令属性|object|false|空（健康）|
|services.service.health\_check.shell|检查命令shell格式|string or string数组|false
|services.service.health\_check.http|检查httpGet返回值|URL|false
|services.service.health\_check.timeout|检查命令超时时间|int(单位s)|false|10|

health_check中shell/http二选一。
### 操作示例
注

1. 以下k2-compose.yml就是“k2-compose文件示例”的内容。
2. 以下所有的命令（除了rm、logs、bash外）都可以接受具体的service名称，也可以缺省，默认是所有的service,如：k2-compose ps busybox1。
3. 同时service支持正则匹配，如：k2-compose ps busybox\* 等价于k2-compose ps busybox1 busybox2
4. k2-compose -f k2-compose.yml，-f接受配置文件，缺省默认是k2-compose.yml, 以下示例都省略-f k2-compose.yml。
5. Image-Status的值只有在镜像有变化时才会提示。
6. 可以通过DOCKER_HOST 修改默认的dockerHost。如果容器没有指定host，就会运行在这个dockerHost上。
7. 可以通过DOCKER_API_VERSION修改docker通信使用的api_version，如DOCKER_API_VERSION=1.23，DOCKER_API_VERSION=‘auto’


#### show
show 有两种状态，

1. show配置文件的拓扑图；
2. show service的配置信息；

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml show
┌k2-compose.yml────────────┬────────────┐
│ host    │ dockerHost     │ services   │
├─────────┼────────────────┼────────────┤
│ as      │ localhost:4243 │ - busybox2 │
├─────────┼────────────────┼────────────┤
│ default │ 127.0.0.1:4243 │ - busybox1 │
└─────────┴────────────────┴────────────┘

root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml show busybox1
┌busybox1──────┬─────────────────────────────┐
│ entrypoint   │ - ping                      │
│              │ - localhost                 │
├──────────────┼─────────────────────────────┤
│ health_check │ shell: echo "ok." && exit 0 │
│              │ timeout: 10                 │
├──────────────┼─────────────────────────────┤
│ image        │ busybox:latest              │
└──────────────┴─────────────────────────────┘
```

#### ps
查看service状态；

这时候容器还没有部署，Service-Status显示的是undeployed，busybox2依赖于busybox1

```shell
root@minion1:~/k2-compose-0.0.4rc1/tests# k2-compose -f k2-compose.yml  ps
+----------+----------------+----------------+--------------+------------+-------+--------------+
| Service  | Host           | Service-Status | Image-Status | Depends-On | Ports | Network-Mode |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox1 | 127.0.0.1:4243 | undeployed     |              |            |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox2 | localhost:4243 | undeployed     |              | - busybox1 |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
```

#### up
启动service，如果镜像不存在的话，会先pull镜像；

-d 参数是让容器在后台启动；

在“k2-compose文件示例”中busybox2的health_check的shell脚本返回值是1（非0），所以busybox2的Service-Status状态是error。


```shell
root@minion1:~/k2-compose-0.0.4rc1/tests# k2-compose -f k2-compose.yml up -d
Creating k2composetest_busybox1_1
Creating k2composetest_busybox2_1
root@minion1:~/k2-compose-0.0.4rc1/tests# k2-compose -f k2-compose.yml ps
+----------+----------------+----------------+--------------+------------+-------+--------------+
| Service  | Host           | Service-Status | Image-Status | Depends-On | Ports | Network-Mode |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox1 | 127.0.0.1:4243 | running        |              |            |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox2 | localhost:4243 | error          |              | - busybox1 |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
```

#### stop
停止service

```
root@minion1:~/k2-compose-0.0.4rc1/tests# k2-compose -f k2-compose.yml stop
Going to stop ALL-Services. Are you sure? [yN] y
Stopping [busybox2] ...
Done.
Stopping [busybox1] ...
Done.
root@minion1:~/k2-compose-0.0.4rc1/tests# k2-compose -f k2-compose.yml ps
+----------+----------------+----------------+--------------+------------+-------+--------------+
| Service  | Host           | Service-Status | Image-Status | Depends-On | Ports | Network-Mode |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox1 | 127.0.0.1:4243 | stopped        |              |            |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox2 | localhost:4243 | stopped        |              | - busybox1 |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
```

#### start
启动service

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml start
Starting [busybox1] ...
Done.
Starting [busybox2] ...
Done.
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml ps
+----------+----------------+----------------+--------------+------------+-------+--------------+
| Service  | Host           | Service-Status | Image-Status | Depends-On | Ports | Network-Mode |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox1 | 127.0.0.1:4243 | running        |              |            |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox2 | localhost:4243 | error          |              | - busybox1 |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
```

#### restart
重启service

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml restart
Stopping [busybox1] ...
Done.
Starting [busybox1] ...
Done.
Stopping [busybox2] ...
Done.
Starting [busybox2] ...
Done.
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml ps
+----------+----------------+----------------+--------------+------------+-------+--------------+
| Service  | Host           | Service-Status | Image-Status | Depends-On | Ports | Network-Mode |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox1 | 127.0.0.1:4243 | running        |              |            |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox2 | localhost:4243 | error          |              | - busybox1 |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
```

#### logs
查看service log

logs 必须指定service名称，支持-f参数，持续显示容器log

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml logs busybox1
Attaching to k2composetest_busybox1_1
busybox1_1  | PING localhost (127.0.0.1): 56 data bytes
busybox1_1  | 64 bytes from 127.0.0.1: seq=0 ttl=64 time=0.039 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=1 ttl=64 time=0.032 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=2 ttl=64 time=0.049 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=3 ttl=64 time=0.036 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=4 ttl=64 time=0.049 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=5 ttl=64 time=0.035 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=6 ttl=64 time=0.037 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=7 ttl=64 time=0.037 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=8 ttl=64 time=0.036 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=9 ttl=64 time=0.038 ms
busybox1_1  | 64 bytes from 127.0.0.1: seq=10 ttl=64 time=0.034 ms
```

#### pull
更新service镜像；

如果有镜像更新，Image-Status会有变化

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml pull
Going to update ALL-Services Images. Are you sure? [yN] y
Pulling busybox1 (busybox:latest)...
latest: Pulling from library/busybox
27144aa8f1b9: Pull complete
Digest: sha256:be3c11fdba7cfe299214e46edc642e09514dbb9bbefcd0d3836c05a1e0cd0642
Status: Downloaded newer image for busybox:latest
Pulling busybox2 (busybox:latest)...
latest: Pulling from library/busybox
Digest: sha256:be3c11fdba7cfe299214e46edc642e09514dbb9bbefcd0d3836c05a1e0cd0642
Status: Image is up to date for busybox:latest
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml ps
+----------+----------------+----------------+--------------+------------+-------+--------------+
| Service  | Host           | Service-Status | Image-Status | Depends-On | Ports | Network-Mode |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox1 | 127.0.0.1:4243 | running        | changed      |            |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox2 | localhost:4243 | error          | changed      | - busybox1 |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
```

#### bash
进入容器；

用的sh,可以手动切换成/bin/bash

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml bash busybox1
#####In [busybox1] Container#####
/ # ls
bin   dev   etc   home  proc  root  sys   tmp   usr   var
/ # exit
#####Out [busybox1] Container#####
```

#### inspect
检查service的镜像信息，如果容器使用的镜像有变化的话，会显示!(NOT MATCH)

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml inspect
┌k2-compose.yml──┬──────────┬──────────────┬─────────────────────┬────────┐
│ Image          │ Service  │ Image-Id     │ Created             │ Labels │
├────────────────┼──────────┼──────────────┼─────────────────────┼────────┤
│ busybox:latest │ busybox2 │ 00f017a8c2a6 │ 2017-03-09T18:28:04 │        │
│ !(NOT MATCH)   │          │              │                     │        │
├────────────────┼──────────┼──────────────┼─────────────────────┼────────┤
│ busybox:latest │ busybox1 │ c30178c5239f │ 2017-06-15T20:42:30 │        │
│                │          │              │                     │        │
└────────────────┴──────────┴──────────────┴─────────────────────┴────────┘
```

#### save
镜像管理工具，非专业人士慎用；此命令将符合Match状态的service的镜像tag后面加一个suffix，然后推送到镜像库

默认是手动选择模式，--no-interaction非交互模式

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml save --suffix test
 Please choose your images for save (press SPACE to mark, ENTER to continue, Ctrl+C to exit):
   Image          | Service  | Image-Id     | Match
   -------------------------------------------------------

 * busybox:latest | busybox1 | c30178c5239f |
   busybox:latest | busybox2 | 00f017a8c2a6 | !(NOT MATCH)

root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml save --suffix test  --no-interaction
List:
do              busybox:latest => busybox:latesttest
skip(not match) busybox:latest => busybox:latesttest
Tag and Push these images.
These service`s image is not ready, please fix it first.
┌Not Ready───────┬──────────┬──────────────┬─────────────────────┬────────┐
│ Image          │ Service  │ Image-Id     │ Created             │ Labels │
├────────────────┼──────────┼──────────────┼─────────────────────┼────────┤
│ busybox:latest │ busybox2 │ 00f017a8c2a6 │ 2017-03-09T18:28:04 │        │
│ !(NOT MATCH)   │          │              │                     │        │
└────────────────┴──────────┴──────────────┴─────────────────────┴────────┘
```

#### rm
删除service时，service必须在stopped状态，然后才能被删除，或者使用-f参数强制删除。

```
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml rm busybox1
Removing [busybox1] ...
ERROR: 409 Client Error: Conflict
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml rm -f busybox1
Removing [busybox1] ...
Done.
root@minion1:~/k2-compose-0.0.4rc2/tests# k2-compose -f k2-compose.yml ps
+----------+----------------+----------------+--------------+------------+-------+--------------+
| Service  | Host           | Service-Status | Image-Status | Depends-On | Ports | Network-Mode |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox1 | 127.0.0.1:4243 | undeployed     |              |            |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
| busybox2 | localhost:4243 | error          | changed      | - busybox1 |       | default      |
+----------+----------------+----------------+--------------+------------+-------+--------------+
```

#### agent
检查host、container状态，并按Telnet API模式打印在终端上，后续有opentsd client处理。

[Writing Data to OpenTSDB](http://opentsdb.net/docs/build/html/user_guide/writing.html)

```
$ k2-compose  -f tests/k2-compose.yml agent --interval 3
put hosts.default 1.5011261104e+12 1 host=default deployment=k2composetest preffix=default
put hosts.as 1.5011261104e+12 1 host=as deployment=k2composetest preffix=default
put containers.busybox2 1.5011261104e+12 142 host=as deployment=k2composetest preffix=default
put containers.busybox1 1.5011261104e+12 210 host=default deployment=k2composetest preffix=default
put hosts.default 1.50112611382e+12 1 host=default deployment=k2composetest preffix=default
put hosts.as 1.50112611382e+12 1 host=as deployment=k2composetest preffix=default
put containers.busybox2 1.50112611382e+12 101 host=as deployment=k2composetest preffix=default
put containers.busybox1 1.50112611382e+12 209 host=default deployment=k2composetest preffix=default

```

### Troubleshooting
