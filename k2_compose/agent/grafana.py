PANEL_ID = 1


class Target(object):
    def __init__(self, alias=None,measurement=None,type=""):
        self.__dict__.update(
            {
                "alias": alias,
                "dsType": "influxdb",
                "groupBy": [
                    {
                        "params": [
                            "$interval"
                        ],
                        "type": "time"
                    },
                    {
                        "params": [
                            "none"
                        ],
                        "type": "fill"
                    }
                ],
                "measurement": measurement,
                "policy": "default",
                "refId": "A",
                "resultFormat": "time_series",
                "select": [
                    [
                        {
                            "params": [
                                "value"
                            ],
                            "type": "field"
                        },
                        {
                            "params": [],
                            "type": "mean"
                        }
                    ]
                ],
                "tags": [
                    {
                        "key": "type",
                        "operator": "=",
                        "value": type
                    }
                ]
            }
        )


class PanelBase(object):
    def __init__(self, title=None, yaxes_l="short", yaxes_r="short",label_l=None,
                 description=None):
        self.__dict__.update(
            {
                "aliasColors": {},
                "bars": False,
                'description':description,
                "datasource": "${DS_INFLUXPROD}",
                "editable": True,
                "error": False,
                "fill": 1,
                "grid": {
                    "threshold1": None,
                    "threshold1Color": "rgba(216, 200, 27, 0.27)",
                    "threshold2": None,
                    "threshold2Color": "rgba(234, 112, 112, 0.22)"
                },
                "id": 1,
                "isNew": True,
                "legend": {
                    "alignAsTable": False,
                    "avg": True,
                    "current": False,
                    "max": True,
                    "min": True,
                    "show": True,
                    "sort": "current",
                    "sortDesc": True,
                    "total": False,
                    "values": True
                },
                "lines": True,
                "linewidth": 1,
                "links": [],
                "nullPointMode": "connected",
                "percentage": False,
                "pointradius": 5,
                "points": False,
                "renderer": "flot",
                "seriesOverrides": [
                  {
                    "alias": "mem_utilization",
                    "yaxis": 2
                  }
                ],
                "span": 4,
                "stack": False,
                "steppedLine": False,
                "timeFrom": None,
                "timeShift": None,
                "title": title,
                "tooltip": {
                    "msResolution": False,
                    "shared": True,
                    "value_type": "cumulative",
                    "sort": 0
                },
                "transparent": True,
                "type": "graph",
                "xaxis": {
                    "show": True
                },
                "yaxes": [
                    {
                        "format": yaxes_l,
                        "label": label_l,
                        "logBase": 1,
                        "max": None,
                        "min": None,
                        "show": True
                    },
                    {
                        "format": yaxes_r,
                        "label": None,
                        "logBase": 1,
                        "max": None,
                        "min": None,
                        "show": True
                    }
                ]

            }
        )
        self.targets=[]


class PanelNew(object):
    def __init__(self, title, measurement, key, value, description=None,delay=30):
        self.__dict__.update(
            {
              "cacheTimeout": None,
              "colorBackground": True,
              "colorValue": False,
              "colors": [
                "rgba(245, 54, 54, 0.9)",
                "rgba(227, 233, 40, 0.86)",
                "rgba(50, 172, 45, 0.97)"
              ],
              "description":description,
              "datasource": "${DS_INFLUXPROD}",
              "format": "none",
              "id": 1,
              "interval": None,
              "links": [],
              "mappingType": 1,
              "mappingTypes": [
                {
                  "name": "value to text",
                  "value": 1
                },
                {
                  "name": "range to text",
                  "value": 2
                }
              ],
              "maxDataPoints": 1,
              "nullPointMode": "connected",
              "nullText": None,
              "postfix": "",
              "postfixFontSize": "50%",
              "prefix": "",
              "prefixFontSize": "50%",
              "rangeMaps": [
                {
                  "from": "0",
                  "text": "undeployed",
                  "to": "null"
                },
                {
                  "from": "1",
                  "text": "stopped",
                  "to": "null"
                },
                  {
                      "from": "2",
                      "text": "error",
                      "to": "null"
                  },
                  {
                      "from": "3",
                      "text": "running",
                      "to": "null"
                  },
                  {
                      "from": "null",
                      "text": "no value",
                      "to": "null"
                  }
              ],
              "span": 2,
              "sparkline": {
                "fillColor": "rgba(31, 118, 189, 0.18)",
                "full": False,
                "lineColor": "rgb(31, 120, 193)",
                "show": False
              },
              "tableColumn": "",
              "targets": [
                {
                  "dsType": "influxdb",
                  "policy": "default",

                  "measurement":measurement,
                  "query": "SELECT last(\"value\") FROM \"%s\" WHERE \"%s\"=\'%s\' AND time > now() - %ds"%(measurement, key, value,delay),
                  "rawQuery": True,
                  "refId": "A",
                  "resultFormat": "time_series",
                  "select": [
                    [
                      {
                        "params": [
                          "value"
                        ],
                        "type": "field"
                      },
                      {
                        "params": [],
                        "type": "last"
                      }
                    ]
                  ],
                  "tags": [
                      {
                          "key": key,
                          "operator": "=",
                          "value": value
                      }
                  ]
                }
              ],
              "thresholds": "2,2.5",
              "title": title,
              "type": "singlestat",
              "valueFontSize": "50%",
              "valueMaps": [
                {
                  "op": "=",
                  "text": "undeployed",
                  "value": "0"
                },
                {
                  "op": "=",
                  "text": "stopped",
                  "value": "1"
                },
                {
                  "op": "=",
                  "text": "error",
                  "value": "2"
                },
                {
                  "op": "=",
                  "text": "running",
                  "value": "3"
                },
                  {
                      "op": "=",
                      "text": "no value",
                      "value": "null"
                  }
              ],
              "valueName": "avg"
            }
        )


class RowBase(object):
    def __init__(self,title):
        self.__dict__.update(
            {
                "collapse": True,
                "editable": True,
                "height": "250px",
                "showTitle": True,
                "title": title
            }
        )
        self.id = 1
        self.panels=[]


class DashboardBase(object):
    def __init__(self,title):
        self.__dict__.update(
            {
                "__inputs": [
                    {
                        "name": "DS_INFLUXPROD",
                        "label": "InfluxProd",
                        "description": "",
                        "type": "datasource",
                        "pluginId": "influxdb",
                        "pluginName": "InfluxDB"
                    }
                ],
                "__requires": [
                    {
                        "type": "panel",
                        "id": "singlestat",
                        "name": "Singlestat",
                        "version": ""
                    },
                    {
                        "type": "panel",
                        "id": "graph",
                        "name": "Graph",
                        "version": ""
                    },
                    {
                        "type": "grafana",
                        "id": "grafana",
                        "name": "Grafana",
                        "version": "3.1.1"
                    },
                    {
                        "type": "datasource",
                        "id": "influxdb",
                        "name": "InfluxDB",
                        "version": "1.0.0"
                    }
                ],
                "id": None,
                "title": title,
                "tags": [
                    title
                ],
                "style": "dark",
                "timezone": "browser",
                "editable": True,
                "hideControls": False,
                "sharedCrosshair": False,
                "time": {
                    "from": "now-1h",
                    "to": "now"
                },
                "annotations": {
                    "list": []
                },
                "refresh": "30s",
                "schemaVersion": 12,
                "version": 15,
                "links": [],
                "gnetId": 331,
                "description": "Performance metrics for %s"%(title)
            }
        )
        self.rows = []


class Dashboard(DashboardBase):
    def __init__(self, title):
        super(Dashboard,self).__init__(title)

    def add_row(self, row):
        self.rows.append(row.__dict__)


class Row(RowBase):

    def __init__(self, title):
        super(Row,self).__init__(title)

    def add_panel(self, panel):
        global PANEL_ID
        panel.id = PANEL_ID
        PANEL_ID += 1
        self.panels.append(panel.__dict__)


class Panel(PanelBase):
    __refid = 65

    def __init__(self, title=None, yaxes_l='short', yaxes_r='short',label_l=None,
                 description=None):
        super(Panel,self).__init__(title,yaxes_l,yaxes_r,label_l,description)
        self.title = title

    def add_target(self, target):
        target.refId = chr(self.__refid)
        self.__refid += 1
        self.targets.append(target.__dict__)