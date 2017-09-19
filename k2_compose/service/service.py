import yaml
from ..k2cutils.basenode import Node
from ..k2cutils.class_utils import cached_property
from terminaltables import SingleTable
from ..common.common import SERVICE_UNDEPLOYED,CONTAINER_STATUS,COLOR

class ComposeService(Node):
    def __init__(self, id='', service=None):
        Node.__init__(self)
        self.type = "container"
        self.id = id
        self._service = service

        self.status_code = SERVICE_UNDEPLOYED
        self.status = CONTAINER_STATUS[SERVICE_UNDEPLOYED]
        self.color = COLOR[self.status_code]

    @cached_property
    def hostname(self):
        return self._service.get('host', 'default')

    @cached_property
    def health_check(self):
        return self._service.get('health_check', {})

    @cached_property
    def s_depends_on(self):
        return self._service.get('s_depends_on', [])

    @cached_property
    def image(self):
        return self._service.get('image', '')

    @cached_property
    def image_name(self):
        index = str(self.image).rfind(':')
        return str(self.image)[:index]

    @cached_property
    def image_tag(self):
        if ":" in str(self.image):
            index = str(self.image).rfind(':')
            return str(self.image)[index + 1:]
        else:
            return 'latest'

    @cached_property
    def ports(self):
        return self._service.get('ports',[])

    @cached_property
    def network_mode(self):
        return self._service.get('network_mode','')

    @cached_property
    def container_name(self):
        return self._service.get('container_name','')

    def show(self):
        table_data = []
        keys = self._service.keys()
        keys.sort()
        for key in keys:
            value = self._service.get(key)
            if isinstance(value, (str, int, bool)) is False:
                value = yaml.dump(value, default_flow_style=False).strip('\n')
            table_data.append([key, value])
        table_instance = SingleTable(table_data, self.id)
        table_instance.inner_heading_row_border = False
        table_instance.inner_row_border = True
        print table_instance.table
