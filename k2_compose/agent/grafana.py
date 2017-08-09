class Target(object):
    def __init__(self, alias=None,measurement=None):
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
                            "null"
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
                    "avg": False,
                    "current": False,
                    "max": False,
                    "min": False,
                    "show": True,
                    "total": False,
                    "values": False
                },
                "lines": True,
                "linewidth": 1,
                "links": [],
                "nullPointMode": "connected",
                "percentage": False,
                "pointradius": 5,
                "points": False,
                "renderer": "flot",
                "seriesOverrides": [],
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


class RowBase(object):
    def __init__(self,title):
        self.__dict__.update(
            {
                "collapse": False,
                "editable": True,
                "height": "250px",
                "showTitle": True,
                "title": title
            }
        )
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
        self._row_id = 1

    def add_row(self, row):
        row.id = self._row_id
        self._row_id += 1
        self.rows.append(row.__dict__)


class Row(RowBase):
    def __init__(self, title):
        super(Row,self).__init__(title)
        self._panel_id = 1

    def add_panel(self, panel):
        panel.id = self._panel_id
        self._panel_id += 1
        self.panels.append(panel.__dict__)


class Panel(PanelBase):
    def __init__(self, title=None, yaxes_l='short', yaxes_r='short'):
        super(Panel,self).__init__(title,yaxes_l,yaxes_r)
        self.title = title
        self._refId = 65

    def add_target(self, target):
        target.refId = chr(self._refId)
        self._refId += 1
        self.targets.append(target.__dict__)