import logging
import os
import tempfile


def atomic_write(data, dst_file_name):
    """Atomic write file by using os.rename() atomic syscall

    This method should be used to avoid race conditions when data must be written to a file, and be sure that no one
     will read that data before it is fully written/flushed.

    :param data: Data to be written.
    :param dst_file_name: File to be atomic written.
    :return: bool True if written was successful, False otherwise.
    """

    try:
        # Open temporary file to write data, don't auto delete after closing it, we gonna os.rename() it.
        tmp_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
    except IOError as io_err:
        logging.getLogger(__name__).critical("Failed to create temporary file: {}".format(str(io_err)))
        return False
    else:
        try:
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_file.close()
            os.rename(tmp_file.name, dst_file_name)
        except IOError as err:
            logging.getLogger(__name__).critical("Failed to write to temporary file: {}".format(str(err)))

            try:
                if not tmp_file.closed:
                    tmp_file.close()

                os.remove(tmp_file.name)
            except:
                pass

            return False
        else:
            return True
