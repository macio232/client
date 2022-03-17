class SyncExecutor:

    def wait_until_finished(self):
        pass

    def execute(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)
