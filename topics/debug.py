
class Debug(object):
    @staticmethod
    def has_item(option, item):
        options = option.split(',')
        return item in options or 'all' in options

    @staticmethod
    def dump_options(options):
        if not Debug.has_item(options.debug, 'option'):
            return

        namelist = options.__dict__.keys()

        for name in namelist:
            value = getattr(options, name)
            print('Option %s' % name)
            print('  origin: %s, value=%r, normalized=%s' % (
                options.origin(name), value, options.normalize(value)))

TOPIC_ENTRY = "Debug"