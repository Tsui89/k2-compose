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
    def __init__(self, title=None, yaxes_l="short", yaxes_r="short"):
        self.__dict__.update(
            {
                "aliasColors": {},
                "bars": False,
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
                "NonePointMode": "connected",
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
                        "label": None,
                        "logBase": 1,
                        "max": None,
                        "min": 0,
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


class PanelHost(object):
    def __init__(self,measurement):
        self.__dict__.update(
            {
                "aliasColors": {},
                "bars": True,
                "datasource": "${DS_INFLUXPROD}",
                "fill": 1,
                "id": 1,
                "legend": {
                    "avg": False,
                    "current": False,
                    "max": False,
                    "min": False,
                    "show": False,
                    "total": False,
                    "values": False
                },
                "lines": False,
                "linewidth": 1,
                "links": [],
                "NonePointMode": "None",
                "percentage": False,
                "pointradius": 5,
                "points": False,
                "renderer": "flot",
                "seriesOverrides": [],
                "span": 12,
                "stack": False,
                "steppedLine": False,
                "targets": [
                    {
                        "alias": "$tag_host",
                        "dsType": "influxdb",
                        "groupBy": [
                            {
                                "params": [
                                    "$__interval"
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
                        "policy": "default",
                        "query": "SELECT \"value\" FROM \"%s\" WHERE $timeFilter GROUP BY \"host\""%(measurement),
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
                                    "type": "mean"
                                }
                            ]
                        ],
                        "tags": []
                    }
                ],
                "thresholds": [],
                "timeFrom": None,
                "timeShift": None,
                "title": "Host Health",
                "tooltip": {
                    "shared": False,
                    "sort": 0,
                    "value_type": "individual"
                },
                "type": "graph",
                "xaxis": {
                    "mode": "series",
                    "name": None,
                    "show": True,
                    "values": [
                        "current"
                    ]
                },
                "yaxes": [
                    {
                        "format": "short",
                        "label": None,
                        "logBase": 1,
                        "max": None,
                        "min": None,
                        "show": True
                    },
                    {
                        "format": "short",
                        "label": None,
                        "logBase": 1,
                        "max": None,
                        "min": None,
                        "show": True
                    }
                ]
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

    def __init__(self, title=None, yaxes_l='short', yaxes_r='short'):
        super(Panel,self).__init__(title,yaxes_l,yaxes_r)
        self.title = title

    def add_target(self, target):
        target.refId = chr(self.__refid)
        self.__refid += 1
        self.targets.append(target.__dict__)