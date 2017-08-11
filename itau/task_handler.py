import logging


class TaskHandler:

    # Required configuration parameters for this specific Instance
    REQUIRED_CFG_PARAMS = ('account_branch_itau', 'account_number_itau', 'account_pin_itau', 'account_cpf_itau')

    def __init__(self, *args, **kwargs):
        self.config = kwargs['config']
        self.logger = logging.getLogger(__name__)

    def setup(self):
        self.logger.info("Checking required configuration parameters...")

        for cfg in TaskHandler.REQUIRED_CFG_PARAMS:
            if cfg not in self.config:
                self.logger.critical("Required configuration param is missing: <{}>".format(cfg))
                return False

        self.logger.info("Configuration is correct.")

        return True

