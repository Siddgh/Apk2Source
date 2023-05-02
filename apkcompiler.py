import argparse
import logging
import datetime
import os
import sys
import config
import subprocess
import shutil
import colorama
from colorama import Fore, Style
import getpass

def setup_parser():
    parser = argparse.ArgumentParser(description='Compile or decompile an APK file')

    parser.add_argument('action', choices=['c', 'd'], help='Specify "c" for compile or "d" for decompile')
    parser.add_argument('input_path', help='Specify the path to the input APK file')

    return parser.parse_args()

def setup_loggers():
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.mkdir(logs_dir)

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_filename = f'{logs_dir}/app_{timestamp}.log'

    logger = logging.getLogger("app_logger")
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)

    error_handler = logging.FileHandler(log_filename)
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    error_handler.setFormatter(error_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    return logger

def setup_output_dir():
    logs_dir = 'output'
    if not os.path.exists(logs_dir):
        os.mkdir(logs_dir)

def check_if_exists(input_path):
    if not os.path.exists(input_path):
        raise Exception(f'{input_path} Path does not exist.')

def validate_input_path_for_decompile(input_path):
    check_if_exists(input_path)
    if not input_path.endswith('.apk'):
        raise Exception('Input file is not an APK file.')

def perform_task(action, apk_file_path):
    if action == 'c':
        perform_apk_compiling(apk_file_path)
    elif action == 'd':
        perform_apk_decompiling(apk_file_path)

def run_on_shell(command, nocommand=False):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        logger.info(result.stdout)

        if result.returncode == 0:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        if nocommand:
            raise Exception("error (code {}): {}".format(e.returncode, e.output))
        else:
            raise Exception("Command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

def check_and_remove_existing_decompiled_code(output_path):
    if os.path.exists(output_path):
        logger.info(f'Existing Decompiled Version found')
        shutil.rmtree(output_path)
        logger.info(f'Removed Existing Decompiled Version')


def perform_apk_decompiling(apk_file_path):
    validate_input_path_for_decompile(args.input_path)
    check_if_exists(config.APKTOOL_PATH)
    
    apk_file_name = os.path.splitext(os.path.basename(apk_file_path))[0]
    output_path = f'output/{apk_file_name}-decompiled'
    
    apktool_decompile_command = f'{config.APKTOOL_PATH} d {apk_file_path} -o {output_path} -f'
    logger.info(f'Running Command: {apktool_decompile_command}')
    result = run_on_shell(apktool_decompile_command)
    
    if result:
        logger.info(Fore.GREEN + 'Successfully Decompiled APK to ' + output_path + Style.RESET_ALL)
        logger.info(Fore.CYAN + 'Make sure you add \'android:extractNativeLibs="true"\' in the AndroidManifest file of your compiled code at the <application> level' + Style.RESET_ALL)
    else:
        logger.error(f'Apktool decompilation failed with command {apktool_decompile_command}')

def create_new_keystore(apk):
    logger.info('Creating a new keystore')
    alias = input("Whats your alias: ")
    validity = input("Keystore Validity: ")
    keystore_name = input("Keystore filename: ")
    name = input('UserName: ')
    organisation_unit = input('Organisation Unit: ')
    organisation = input('Organisation: ')
    city = input('City: ')
    state = input('State: ')
    country = input('Country (eg US): ')

    output_path = f'output/{keystore_name}.keystore'
    command = f'keytool -genkeypair -alias {alias} -keyalg RSA -keysize 2048 -validity {validity} -keystore {keystore_name}.keystore -noprompt -storepass {getpass.getpass("Password: ")} -keypass {getpass.getpass("Password: ")} -dname "CN={name}, OU={organisation_unit}, O={organisation}, L={city}, S={state}, C={country}" -destkeystore {output_path}'
    
    result = run_on_shell(command, nocommand=True)

    if result:
        logger.info(Fore.GREEN + 'Keystore Created Successfully at ' + output_path + Style.RESET_ALL)
        use_existing_keystore(output_path, alias, apk)
    else:
        logger.error(f'Failed to create keystore')

def use_existing_keystore(keystore_path, alias, apk):
    logger.info(f'Signing APK at {apk} with keystore {keystore_path}')
    
    check_if_exists(keystore_path)
    check_if_exists(f'{config.ANDROID_SDK_TOOLS}/apksigner')
    check_if_exists(apk)

    apk_file_name = os.path.splitext(os.path.basename(apk))[0]
    apk_file_name = str(apk_file_name).replace('-zipaligned', '')

    output_path = f'output/{apk_file_name}-signed.apk'
    
    command = f'{config.ANDROID_SDK_TOOLS}/apksigner sign --ks {keystore_path} --ks-key-alias {alias} --ks-pass pass:{getpass.getpass("Password: ")} --key-pass pass:{getpass.getpass("Password: ")} --out {output_path} {apk}'
    result = run_on_shell(command)

    if result:
        logger.info(Fore.GREEN + 'Your Signed APK is ready at ' + output_path + Style.RESET_ALL)
    else:
        logger.error(f"Failed to sign the apk with command {command}")

def start_apk_signing_process(apk):
    check_if_exists(apk)
    logger.info(f'Starting APK Signing Process for {apk}')
    message_prompt = """
    Do you want to create a new keystore or use an existing one?
    1. Create new keystore
    2. Use an existing keystore
    3. No thanks, I'm done
    """

    user_choice = input(message_prompt)
    if user_choice == '1':
        create_new_keystore(apk)
    elif user_choice == '2':
        keystore_path = input('Keystore Path: ')
        alias = input('Alias: ')
        use_existing_keystore(keystore_path, alias,apk)
    elif user_choice == '3':
        logger.info(f'Your unsigned apk file is stored at {apk}')
    else:
        logger.error('Invalid input. Please enter 1 or 2.')


def start_zipalign_process(apk):
    check_if_exists(apk)
    check_if_exists(f'{config.ANDROID_SDK_TOOLS}/zipalign')
    apk_file_name = os.path.splitext(os.path.basename(apk))[0]
    apk_file_name = str(apk_file_name).replace('-unsigned', '')
    logger.info(f'Starting zipalign process for {apk}')
    output_path = f'output/{apk_file_name}-zipaligned.apk'
    zipalign_command = f'{config.ANDROID_SDK_TOOLS}/zipalign -p -f 4 {apk} {output_path}'
    result = run_on_shell(zipalign_command)
    
    if result:
        logger.info(Fore.GREEN + 'Successfully Zipaligned APK to ' + output_path + Style.RESET_ALL)
        start_apk_signing_process(output_path)
    else:
        logger.error(f'Failed to zipalign the apk file with command {zipalign_command}')



def perform_apk_compiling(decompiled_code_dir):
    logger.info(f'Compiling the Code at {decompiled_code_dir}')
    check_if_exists(decompiled_code_dir)
    dir_name = os.path.basename(decompiled_code_dir)
    dir_name = str(dir_name).replace('-decompiled', '')
    output_path = f'output/{dir_name}-unsigned.apk'
    apktool_compile_command = f'{config.APKTOOL_PATH} b {decompiled_code_dir} -o {output_path} --use-aapt2'
    result = run_on_shell(apktool_compile_command)

    if result:
        logger.info(Fore.GREEN + 'Successfully Compiled APK to ' + output_path + Style.RESET_ALL)
        start_zipalign_process(output_path)
    else:
        logger.error(f'Apktool compilation failed with command {apktool_compile_command}')


if __name__ == "__main__":
    args = setup_parser()
    logger = setup_loggers()
    colorama.init()
    setup_output_dir()
    try:
        perform_task(args.action, args.input_path)
    except Exception as e:
        logger.error(f'Error: {str(e)}')