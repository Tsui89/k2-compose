
class Dashboard(object):
    def __init__(self, title, overwrite=False, timezone='browser',
                 schemaVersion=6, version=0, tags=None, **kwargs):
        self.id = 1
        self.title = title
        self.overwrite = overwrite
        self.timezone = timezone
        self.schemaVersion = schemaVersion
        self.version = version
        self.tags = tags
        self.rows = []
        self.__dict__.update(kwargs)

    def add_row(self, row):
        self.rows.append(row.__dict__)



class Row(object):
    def __init__(self, title, collapse=True, editable=True,
                 height="200px"):
        self.title = title
        self.collapse = collapse
        self.editable = editable
        self.height = height
        self.panels = []
        self.id = 1

    def add_panel(self, panel):
        panel.id = self.id
        self.id += 1
        self.panels.append(panel.__dict__)


class Panel(object):
    def __init__(self, title, editable=True, fill=0, type='graph',
                 yaxes_l='short', yaxes_r='short'):
        self.title = title
        self.editable = editable
        self.fill = fill
        self.type = type
        self.targets = []
        self.id = 1
        self.datasource = 'Demo'
        self.lines = True
        self.yaxes=[
            {'format':yaxes_l},
            {'format':yaxes_r}
        ]


    def add_target(self, target):

        self.targets.append(target.__dict__)


class Target(object):
    def __init__(self, metric,measurement,alias=None):
        self.metric = metric
        self.dsType = "influxdb"
        self.measurement = measurement
        self.groupBy = []
        self.alias=alias
        self.__dict__.update({"groupBy": [
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
              ]})
        self.__dict__.update({  "select": [
                [
                  {
                    "params": [
                      "value"
                    ],
                    "type": "field"
                  }
                ]
              ]})