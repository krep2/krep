
class Debug(object):
    @staticmethod
    def has_item(option, item):
        options = (option or '').split(',')
        return item in options or 'all' in options

    @staticmethod
    def dump_options(options):
        if not Debug.has_item(options.debug, 'option'):
            return

        namelist = options.__dict__.keys()

        print('\nOptions Dumping')
        print('-------------------------')
        for name in namelist:
            value = getattr(options, name)
            print('Option %s' % name)
            print('  origin: %s, value=%r, normalized=%s' % (
                options.origin(name), value, options.normalize(value)))

    @staticmethod
    def dump_pattern(options, patterns):
        if Debug.has_item(options.debug, 'pattern'):
            print('\nPatterns Dumping')
            print('-------------------------')
            print(str(patterns))


TOPIC_ENTRY = "Debug"