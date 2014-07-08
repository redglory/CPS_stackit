from .main import Stackit

def autoload():
    return Stackit()

config = [{
    'name': 'stackit',
    'groups': [
        {
            'tab': 'notifications',
            'list': 'notification_providers',
            'name': 'stackit',
            'label': 'Stackit',
            'description': 'Stack movies using ffmpeg, merging part files into single movie file',
            'options': [
                {
                    'name': 'enabled',
                    'default': 0,
                    'type': 'enabler',
                },
            ],
        }
    ],
}]
