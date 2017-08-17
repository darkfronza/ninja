""" Valid return codes used by operations (TED/TEF/DOC)

    If any operation returns OP_CUSTOMER_NOT_FOUND,
    that means customer must be added and the operation must be run again.
"""

OP_SUCCESS = 0
OP_CUSTOMER_NOT_FOUND = 1
OP_TIMEOUT = 2
OP_FAILED = 3
