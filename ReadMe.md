
#### 最新版本0.1.7rc2

#### 简介
k2-compose集成了docker-compose==1.14.0的基础功能，包括

> up 启动service。如果镜像不存在，会先pull镜像

> stop 停止service。

> start 启动停止的service。

> restart 重启service。

> rm 删除service

> logs 查看log

> pull pull镜像

优化增加了以下功能

> inspect 检查镜像信息

> ps 检查service状态

> bash 进入start状态的service

> show 查看service分布图，或者查看service配置

> save 将service的所使用的镜像重新tag／push

> agent 将host／service的状态按照opentsdb telnet方式打印到终端上，或直接发送到opentsdb http接口

> help 展示service的说明文档

配置文件支持docker-compose原生、k2-compose定制化，这两种配置文件格式。

安装：

sudo pip install k2-compose==0.1.7rc2

或者使用国内豆瓣镜像源

sudo pip install k2-compose==0.1.7rc2 -i http://pypi.douban.com/simple \-\-trusted-host pypi.douban.com

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
|services.service.health\_check.socket|socket连接状态|URL|false
|services.service.health\_check.timeout|检查命令超时时间|int(单位s)|false|10|

health_check中shell/http二选一。
### 操作示例
注

1. docker daemon需要对外暴露服务，添加启动参数 -H unix:///var/run/docker.sock -H tcp://0.0.0.0:4243
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
停止service, -t/--time 参数指定超时时间，强制stop。

```
root@minion1:~/k2-compose-0.0.4rc1/tests# k2-compose -f k2-compose.yml stop -t 3
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

失败：

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

成功：

```
$ k2-compose save --suffix test
List:
do              10.1.10.48:5000/busybox:latest => 10.1.10.48:5000/busybox:latesttest
Tagging 10.1.10.48:5000/busybox:latest => 10.1.10.48:5000/busybox:latesttest ...
Pushing...
busybox1 => sha256:f6c84d454a241799db9d9e1e2dd99ae17fe9fd915a14aca24812b103ce2122c5
Push all done.

┌Done────────────────────────────┬──────────┬──────────────┬─────────────────────┬────────┐
│ Image                          │ Service  │ Image-Id     │ Created             │ Labels │
├────────────────────────────────┼──────────┼──────────────┼─────────────────────┼────────┤
│ 10.1.10.48:5000/busybox:latest │ busybox1 │ efe10ee6727f │ 2017-07-19T23:34:19 │        │
└────────────────────────────────┴──────────┴──────────────┴─────────────────────┴────────┘
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
检查host、container状态以及cpu/memory使用情况，并按Telnet API模式打印在终端上，也可以使用--opentsdb-http参数指定opentsdb服务地址，直接发送。

之后会在本地生成dashboard.json，grafana导入这个dashboard.json即可。

[Writing Data to OpenTSDB](http://opentsdb.net/docs/build/html/user_guide/writing.html)

```
$ k2-compose agent --prefix gw
put gw.k2composetest.hosts.default 1501743176 1 host=default
put gw.k2composetest.hosts.as 1501743176 1 host=as
put gw.k2composetest.containers.busybox2 1501743176 76 host=as container=busybox2
put gw.k2composetest.containers.busybox2.mem_limit 1501743176 32051 host=as container=busybox2
put gw.k2composetest.containers.busybox2.mem_usage 1501743176 0 host=as container=busybox2
put gw.k2composetest.containers.busybox2.mem_percent 1501743176 0.0 host=as container=busybox2
put gw.k2composetest.containers.busybox2.cpu_percent 1501743176 0.01 host=as container=busybox2
put gw.k2composetest.containers.busybox1 1501743176 201 host=default container=busybox1
put gw.k2composetest.containers.busybox1.mem_limit 1501743176 32051 host=default container=busybox1
put gw.k2composetest.containers.busybox1.mem_usage 1501743176 0 host=default container=busybox1
put gw.k2composetest.containers.busybox1.mem_percent 1501743176 0.0 host=default container=busybox1
put gw.k2composetest.containers.busybox1.cpu_percent 1501743176 0.01 host=default container=busybox1

$ k2-compose agent --prefix cwc --opentsdb-http localhost:4242 --interval 3
send success [{'timestamp': 1502075250, 'metric': 'cwc.demo.hosts.default', 'value': 1L, 'tags': {'host': 'default'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.hosts.as', 'value': 1L, 'tags': {'host': 'as'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.influxdb', 'value': -6L, 'tags': {'host': 'as', 'container': 'influxdb'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.influxdb.mem_limit', 'value': 1999L, 'tags': {'host': 'as', 'container': 'influxdb'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.influxdb.mem_usage', 'value': 32L, 'tags': {'host': 'as', 'container': 'influxdb'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.influxdb.mem_percent', 'value': 1.64, 'tags': {'host': 'as', 'container': 'influxdb'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.influxdb.cpu_percent', 'value': 0.29, 'tags': {'host': 'as', 'container': 'influxdb'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.grafana', 'value': 19L, 'tags': {'host': 'default', 'container': 'grafana'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.grafana.mem_limit', 'value': 1999L, 'tags': {'host': 'default', 'container': 'grafana'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.grafana.mem_usage', 'value': 19L, 'tags': {'host': 'default', 'container': 'grafana'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.grafana.mem_percent', 'value': 0.97, 'tags': {'host': 'default', 'container': 'grafana'}}, {'timestamp': 1502075250, 'metric': 'cwc.demo.containers.grafana.cpu_percent', 'value': 0.04, 'tags': {'host': 'default', 'container': 'grafana'}}]
```

#### help

在build镜像的时候，将相关的txt文档放入镜像的/docs/目录下，使用k2-compose help <serivce> 就可以显示出来，供镜像使用者查看。

```
$ k2-compose help docs
docs Help:

   ---docs/readme.txt Begin---
   This is Manual of busybox.

   HaHaHaHa

   test for service help
   ---docs/readme.txt End---
End
```

### Troubleshooting

> 如果显示Connect Error,解决方法：
>> 1. 检查docker daemon启动参数有没有加-H tcp://0.0.0.0:4243 -H unix:///var/run/docker.sock
>> 2. 执行docker version检查api version。然后使用DOCKER_API_VERSION=\<api version\> k2-compose xxx
