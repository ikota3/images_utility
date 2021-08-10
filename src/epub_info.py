import epub_meta
import fire
import glob
import os
import re
import shutil
import time
import zipfile
from alive_progress import alive_bar
from enum import Enum, auto
from lxml import etree
from utils import setup_logger
from validator import is_dir, is_bool, is_file

logger = setup_logger(__name__)


class Platform(Enum):
    """Platform enum."""
    WINDOWS = auto()
    LINUX = auto()


def replace_fullwidth_alpha_numeral_to_halfwidth(text: str):
    """
    Replace full-width alpha-numeral characters to half-width characters.

    Args:
        text (str): Text to replace.

    Returns:
        str: Replaced text.
    """
    return re.sub(r'[Ａ-Ｚａ-ｚ０-９]', lambda mathobj: chr(ord(mathobj.group(0)) - 0xFEE0), text)


def replace_unsafe_symbol_to_safe_symbol(text: str):
    """
    Replace unsafe symbol characters(on NTFS) to safe symbol characters.

    Example:
        `<`  -> `＜`
        `>`  -> `＞`
        `:`  -> `：`
        `"`  -> `”`
        `/`  -> `／`
        `\\`  -> `￥`
        `!`  -> `！`
        `?`  -> `？`
        `*`  -> `＊`

    Args:
        text (str): Text to replace.

    Returns:
        str: Replaced text.

    Note:
        `!` is a valid character, but I'll adjust to `?`.
    """
    return re.sub(r'[<>:"\/\\|!?*]', lambda mathobj: chr(ord(mathobj.group(0)) + 0xFEE0), text)


def replace_fullwidth_round_brackets_to_halfwidth(text: str):
    """
    Replace full-width round brackets to half-width brackets.

    Example:
        `（`  ->  `(`
        `）`  ->  `)`

    Args:
        text (str): Text to replace.

    Returns:
        str: Replaced text.
    """
    return re.sub(r'[（）]', lambda mathobj: chr(ord(mathobj.group(0)) - 0xFEE0), text)


def pad_numeric_only_string_enclosed_in_round_brackets(text: str):
    """
    Pad numeric-only strings enclosed in round brackets with spaces on both sides or behind
    Or numeric-only string enclosed in round brackets when the extension appears immediately after the brackets.

    Example:
        xxx (1) yyy.epub -> xxx 01 yyy.epub
        xxx(1) yyy.epub  -> xxx 01 yyy.epub
        xxx (1).epub     -> xxx 01.epub

    Args:
        text (str): Text to pad.

    Returns:
        text (str): Padded text.
    """
    match_result = re.search(r'\s*\(\s*(\d+)\s*\)\s+', text)
    if match_result:
        number = f' {str(int(match_result.group(1))).zfill(2)} '
        text = re.sub(r'\s*\(\s*\d+\s*\)\s*', number, text)

    match_result = re.search(r'\s*\(\s*(\d+)\s*\)\s*\.epub', text)
    if match_result:
        number = f' {str(int(match_result.group(1))).zfill(2)}'
        text = re.sub(r'\s*\(\s*\d+\s*\)\s*(?=\.epub)', number, text)

    return text


def pad_kanji_number(text: str):
    """
    Pad kanji number.

    Args:
        text (str): Text to pad.

    Returns:
        text (str): Padded text.
    """
    kanji_numbers = ['壱', '弐', '参', '肆', '伍', '陸', '漆', '捌', '玖', '拾', '什']
    kanji_mapping = dict(zip(kanji_numbers, list(map(str, range(1, 11))) + ['10']))
    match_result = re.search(r'\s*([' + '|'.join(kanji_numbers) + r'])\s*巻?\s*', text)
    if match_result:
        number = f' {kanji_mapping.get(match_result.group(1))} '
        text = re.sub(r'\s*[' + '|'.join(kanji_numbers) + r']\s*巻?\s*', number, text)

    return text


def format_book_author(book_author: str) -> str:
    """
    Format book author.

    Args:
        book_author (str): Book author.

    Returns:
        str: Formatted book author.
    """
    book_author = replace_fullwidth_alpha_numeral_to_halfwidth(book_author)
    book_author = replace_unsafe_symbol_to_safe_symbol(book_author)

    return book_author


def format_book_title(book_title: str) -> str:
    """
    Format book title.

    Args:
        book_title (str): Book title.

    Returns:
        str: Formatted book title.

    Note:
        The format pattern will only works on EPub file.
    """
    book_title = replace_fullwidth_alpha_numeral_to_halfwidth(book_title)
    book_title = replace_unsafe_symbol_to_safe_symbol(book_title)
    book_title = replace_fullwidth_round_brackets_to_halfwidth(book_title)

    # Replace unnecessary characters
    # book_title = re.sub(r'【.+?】', '', book_title)
    book_title = re.sub(r'【.+?(付き|増量版|無料版?|出版|誌版|特別版?|特典付き?|漫画付き?)】', '', book_title)
    book_title = re.sub(r'[(＜〈].*?(BOOKS|Creative|DX版?|GAMES|JOKER|Network|NOVELS|NOVEL 0|Publishing|エイジ|エクストラ|コミック|シリーズ|ス|ノベルズ|ラノベ|限定版|小説|新装版|電子版|特典付き|特別版|文芸|文庫J?|編集部)[〉＞)]', '', book_title)
    book_title = re.sub(r'[：:]', ' ', book_title)
    book_title = re.sub(r'\s+', ' ', book_title)

    # Pad number
    book_title = pad_numeric_only_string_enclosed_in_round_brackets(book_title)
    book_title = pad_kanji_number(book_title)

    # Padding symbol numbers
    match_result = re.search(r'\s*([①-⑨])\s*巻?\s*', book_title)
    if match_result:
        number = f' {chr(ord(match_result.group(1)) - 0x242F).zfill(2)} '
        book_title = re.sub(r'\s*[①-⑨]\s*巻?\s*', number, book_title)

    match_result = re.search(r'\s*([⑴-⑼])\s*巻?\s*', book_title)
    if match_result:
        number = f' {chr(ord(match_result.group(1)) - 0x2443).zfill(2)} '
        book_title = re.sub(r'\s*[⑴-⑼]\s*巻?\s*', number, book_title)

    match_result = re.search(r'\s*([⒈-⒐])\s*巻?\s*', book_title)
    if match_result:
        number = f' {chr(ord(match_result.group(1)) - 0x2457).zfill(2)} '
        book_title = re.sub(r'\s*[⒈-⒐]\s*巻?\s*', number, book_title)

    match_result = re.search(r'\s*([⓵-⓽])\s*巻?\s*', book_title)
    if match_result:
        number = f' {chr(ord(match_result.group(1)) - 0x24C4).zfill(2)} '
        book_title = re.sub(r'\s*[⓵-⓽]\s*巻?\s*', number, book_title)

    # Padding numeric-only string in front of the extension
    # e.g., xxx1巻.epub -> xxx 01.epub
    # e.g., xxx1.epub -> xxx 01.epub
    match_result = re.search(r'(?<=\s)?(\d+)(?=巻?\s*\.epub)', book_title)
    if match_result:
        number = f' {str(int(match_result.group(1))).zfill(2)}'
        book_title = re.sub(r'\s*\d+巻?\s*(?=\.epub)', number, book_title)

    # Remove spaces before extension
    book_title = re.sub(r'\s+', ' ', book_title)
    book_title = re.sub(r'\s+(?=\.epub)', '', book_title)

    return book_title


def get_epub_info(filepath: str) -> dict:
    # metadata = epub_meta.get_epub_metadata(filepath)
    # return metadata
    parser = etree.XMLParser(remove_comments=False, encoding='utf-8')
    epub_info_xml: etree.ElementTree = etree.XML(
        epub_meta.get_epub_opf_xml(filepath),
        parser
    )
    namespace = {
        'ns': 'http://www.idpf.org/2007/opf',
        'dc': 'http://purl.org/dc/elements/1.1/'
    }

    # from xml.etree import ElementTree
    # updated_title = re.search(r'(?<=name="Updated_Title" content=")(.+?)(?=")', etree.tostring(epub_info_xml, encoding='CP932').decode('cp932'))
    # if updated_title:
    #     title = updated_title.group(1)
    # else:
    #     title = epub_info_xml.xpath('//ns:metadata/dc:title/text()', namespaces=namespace)[0]
    title = epub_info_xml.xpath('//ns:metadata/dc:title/text()', namespaces=namespace)[0]
    author = epub_info_xml.xpath("//ns:metadata/dc:creator/text()", namespaces=namespace)
    genre = epub_info_xml.xpath("//ns:metadata/ns:meta[@name='book-type']/@content", namespaces=namespace)
    ret_val = {
        'title': title,
        'author': re.sub(r'( |　)', '', author[0]) if len(author) != 0 else 'NotFound',
        'genre': genre[0].upper() if genre else 'NotFound'
    }
    return ret_val


class EPubInfo():
    """Class for EPub utilities."""

    def __init__(self, input_dir_or_file: str = '', platform: Platform = Platform.WINDOWS):
        self.input_dir_or_file = input_dir_or_file

    def __common_args_is_valid(self) -> bool:
        is_valid = True

        if not is_dir(self.input_dir_or_file) and not is_file(self.input_dir_or_file):
            logger.info('You must type a valid directory or a file for INPUT_DIR_OR_FILE.')
            is_valid = False

        if is_file(self.input_dir_or_file) and os.path.splitext(self.input_dir_or_file)[1].upper() != '.EPUB':
            logger.info('You must specify an EPub file, if the given INPUT_DIR_OR_FILE was intended to be a file.')
            is_valid = False

        return is_valid

    def __show_rename_args_is_valid(self, genre) -> bool:
        is_valid = True

        if not self.__common_args_is_valid():
            is_valid = False

        if not is_bool(genre):
            logger.info('You must just type -g flag. No need to type a parameter.')
            logger.info('Input parameter is not valid. Try again.')
            is_valid = False

        return is_valid

    def __unpack_args_is_valid(self, output_dir: str) -> bool:
        is_valid = True

        if not self.__common_args_is_valid():
            is_valid = False

        if not is_dir(output_dir):
            logger.info('You must type a valid directory for OUTPUT_DIR.')
            is_valid = False

        return is_valid

    def __get_filenames(self) -> list[str]:
        if is_file(self.input_dir_or_file):
            return [os.path.basename(self.input_dir_or_file)]

        return os.listdir(self.input_dir_or_file)

    def __get_dirname(self) -> str:
        if is_file(self.input_dir_or_file):
            return os.path.dirname(self.input_dir_or_file)

        return self.input_dir_or_file

    def show_rename(self, genre: bool = True):
        """Show rename command for EPub.

        Get the title and other information from EPub's OPF container XML, and build a rename command.

        Usage:
            python src/epub_info.py show_rename -i "path/to/dir or file" --genre
                Show rename command and the book's genre.

            python src/epub_info.py show_rename -i "path/to/dir or file" --nogenre
                Show rename command. but don't show the book's genre.

            python src/epub_info.py show_rename -h
                Show this help message.

        Note:
            It will NOT look recursively.
        """

        if not self.__show_rename_args_is_valid(genre):
            logger.info('Input parameter is not valid. Try again.')
            return

        for filename in self.__get_filenames():
            filepath = os.path.join(self.__get_dirname(), filename)

            # Skip directory or not an EPub file
            if os.path.isdir(filepath) or os.path.splitext(filepath)[1].upper() != '.EPUB':
                continue

            # Get EPub info
            epub_info = get_epub_info(filepath)

            print(f'{"Genre: " + epub_info.get("genre") + " " if genre else ""}rename "{os.path.basename(filepath)}" "[{format_book_author(epub_info.get("author"))}]{format_book_title(epub_info.get("title") + ".epub")}"'.encode('cp932', errors='backslashreplace').decode('cp932'))

    def unpack(self, output_dir: str = ''):
        """Unpack all images in EPub file.

        Unpack all images in EPub file.

        EPub file directory tree
        -> {output_dir}/{{first_directory_name}}/{{second_directory_name}}/* Extracted EPub directory tree will look like this
        -> {output_dir}/{book_title}/{{second_directory_name}}/*             Rename the first_directory_name to book's title
        -> {output_dir}/{book_title}/*                                       Move files in the second_directory_name directory, directly below to the book's title directory
        -> {output_dir}/{book_title}/*                                       Delete the directory where the images were stored

        Usage:
            python src/epub_info.py unpack -i "path/to/dir or file" -o "path/to/output"
                Unpack all images in EPub files from given target directory or file, and output to given output directory.

            python src/epub_info.py unpack -h
                Show this help message.

        Note:
            It will NOT look recursively.
        """

        if not output_dir:
            if is_file(self.input_dir_or_file):
                output_dir = os.path.dirname(self.input_dir_or_file)
            else:
                output_dir = self.input_dir_or_file

        if not self.__unpack_args_is_valid(output_dir):
            logger.info('Input parameter is not valid. Try again.')
            return

        for filename in self.__get_filenames():
            filepath = os.path.join(self.__get_dirname(), filename)
            # Skip directory or not an EPub file
            if os.path.isdir(filepath) or os.path.splitext(filepath)[1].upper() != '.EPUB':
                continue

            with zipfile.ZipFile(filepath, mode='r', compression=zipfile.ZIP_DEFLATED, allowZip64=False) as epub_file:
                basename_without_ext = os.path.splitext(os.path.basename(filepath))[0]

                # Extract image files in EPub file
                logger.info('\n' + ('#' * 25))
                logger.info(f'EXTRACTING... {basename_without_ext}')
                imagepaths_in_epub = [
                    path.filename for path in epub_file.filelist
                    if path.filename.endswith(('.jpg', '.jpeg', '.png', '.gif')) and not re.search(r'[\\\/]public(image|_image| image)s?', path.filename)
                ]
                with alive_bar(len(imagepaths_in_epub), bar='filling') as bar:
                    for imagepath_in_epub in imagepaths_in_epub:
                        epub_file._extract_member(imagepath_in_epub, output_dir, None)
                        bar()
                # epub_file.extractall(output_dir, imagepaths_in_epub)
                logger.info(f'EXTRACT COMPLETE! {basename_without_ext}')

                # Rename the first directory name to book's title
                first_directory_name = imagepaths_in_epub[0].split('/')[0]
                while True:
                    try:
                        before_filename = os.path.join(output_dir, first_directory_name)
                        after_filename = os.path.join(output_dir, basename_without_ext)
                        os.rename(before_filename, after_filename)
                        logger.info(f'Rename {before_filename} -> {after_filename}')
                        break
                    except OSError:
                        logger.error('Exception occurred in renaming...')
                        logger.error('Try again...')
                        time.sleep(1)

                # Move the images in the directory to directly below to the book's title directory
                second_directory_name = imagepaths_in_epub[0].split('/')[1]
                images_to_move = glob.glob(os.path.join(glob.escape(os.path.join(output_dir, basename_without_ext, second_directory_name)), '*'))
                logger.info(f'Move {os.path.join(output_dir, basename_without_ext, second_directory_name, "*.jpg")} -> {os.path.join(output_dir, basename_without_ext, "*.jpg")}')
                for filename in images_to_move:
                    shutil.move(filename, os.path.join(output_dir, basename_without_ext, os.path.basename(filename)))

                # Delete image directory
                while True:
                    delete_directory = os.path.join(output_dir, basename_without_ext, second_directory_name)
                    logger.info(f'Delete {delete_directory}')
                    try:
                        os.rmdir(delete_directory)
                        break
                    except OSError:
                        logger.error('Exception occurred at deleting...')
                        logger.error('Try again...')
                        time.sleep(1)

    def count_image(self):
        """Count images in EPub file.

        Usage:
            python src/epub_info.py count_image -i "path/to/dir or file"
                Count and show the images in in EPub files from given target directory.

            python src/epub_info.py count_image -h
                Show this help message.

        Note:
            It will NOT look recursively.
        """

        if not self.__common_args_is_valid():
            logger.info('Input parameter is not valid. Try again.')
            return

        for filename in self.__get_filenames():
            filepath = os.path.join(self.__get_dirname(), filename)
            # Skip directory or not an EPub file
            if os.path.isdir(filepath) or os.path.splitext(filepath)[1].upper() != '.EPUB':
                continue

            with zipfile.ZipFile(filepath) as epub_file:
                basename_without_ext = os.path.splitext(os.path.basename(filepath))[0]
                imagepaths_in_epub = [
                    path.filename for path in epub_file.filelist if path.filename.endswith(('.jpg', '.jpeg', '.png'))
                ]
                print(f'{len(imagepaths_in_epub): 4}: {basename_without_ext}')


def main():

    fire.Fire(EPubInfo)

    # (?<=rename )(".+?")(?= ) (".+")$
    # $2 $1


if __name__ == '__main__':
    main()
