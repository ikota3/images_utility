import os
import fire
import shutil
from alive_progress import alive_bar
from validator import is_dir, is_bool
from utils import show_info, setup_logger, UserResponse, ask


logger = setup_logger(__name__)

SUPPORTED_FORMAT_TYPES = ['zip']


class CompressDir():
    def __init__(
            self,
            input_dir: str = '',
            output_dir: str = '',
            format_type: str = 'zip',
            yes: bool = False
    ):
        """Initialize

        Args:
            input_dir (str): Target directory. Defaults to ''.
            output_dir (str): Output directory. Default is the same as input_dir.
            format_type (str): Compressed file format type. Defaults to 'zip'.
            yes (bool): Flag for asking to execute or not. Defaults to False.
        """
        self.input_dir: str = input_dir
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = input_dir
        self.format_type = format_type.lower()
        self.yes: bool = yes

    def _input_is_valid(self) -> bool:
        """Validator for input.

        Returns:
            bool: True if is valid, False otherwise.
        """
        is_valid = True

        # Check input_dir
        if not is_dir(self.input_dir):
            logger.error(
                'You must type a valid directory for INPUT DIRECTORY. (-i, --input_dir)'
            )
            is_valid = False

        # Check output_dir
        if not is_dir(self.output_dir):
            logger.error(
                'You must type a valid directory for OUTPUT DIRECTORY. (-o, --output_dir)'
            )
            is_valid = False

        # Check format_type
        if self.format_type not in SUPPORTED_FORMAT_TYPES:
            logger.error(
                f'You must type a valid format type. The supported format types are {",".join(SUPPORTED_FORMAT_TYPES)}. (-f, --format_type)'
            )
            is_valid = False

        # Check yes
        if not is_bool(self.yes):
            logger.error(
                'You must just type -y flag. No need to type a parameter. (-y, --yes)'
            )
            is_valid = False

        return is_valid

    def compress(self):
        """Compress each directories directly below to the input directory.

        Synopsis:
            python src/compress_dir.py compress -i 'path/to/dir' [OPTIONS]

        Description:
            Compress each directories directly below to the given input directory.
            The default compress file format is ZIP.

        Options:
            -o, --output_dir <path/to/dir>      Where the compressed file will be output.
                                                If this option was not specified, it will be the same as input directory(-i, --input_dir).

            -f, --format_type <format-type>     What kind of format to use.
                                                The avaliable format types is zip only.
                                                If this option was not specified, it will be set to ZIP.

            -y, --yes                           Execute immediately without asking.
        """
        show_info(self)
        if not self._input_is_valid():
            logger.info('Input parameter is not valid. Try again.')
            return

        dirs = os.listdir(self.input_dir)
        total_dirs = len(dirs)
        logger.info(f'{total_dirs} directories will be executed.')

        if not self.yes:
            user_response = ask()
            if user_response == UserResponse.NO:
                logger.info('Abort...')
                return

        logger.info('Start Compressing each directories...')

        with alive_bar(total_dirs, bar='filling', spinner='dots_waves') as bar:
            for i, directory in enumerate(dirs):
                logger.info(f'Compressing {directory}')
                compressed_filename = shutil.make_archive(
                    base_name=os.path.join(self.output_dir, directory),
                    format=self.format_type,
                    root_dir=os.path.join(self.output_dir, directory)
                )
                logger.info(f'Compress complete! The {self.format_type} file is located at {compressed_filename}')
                bar()

        logger.info('Abort...')


if __name__ == '__main__':
    fire.Fire(CompressDir)
