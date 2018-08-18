# todo comment methods in this file
import os

from datetime import datetime
from hashlib import md5
from django.core.files import File
from predictor.predict_controller import make_prediction
from predictor.models import Result


def get_md5_from_two_files(menu, people):

    hash_md5 = md5()

    for chunk in menu.chunks():
        hash_md5.update(chunk)

    hash_md5.update(b' salt ')

    for chunk in people.chunks():
        hash_md5.update(chunk)

    return hash_md5.hexdigest()


# todo add csv and pandas in writing
def make_prediction_file(menu_data, people_data, hash_key):
    result = make_prediction(menu_data, people_data)

    if not os.path.exists('prediction'):
        os.makedirs('prediction')

    result_file = File(open('prediction/' + hash_key + '.csv', 'wb+'))

    result_file.write(result)

    return result_file


# todo add any cash cleaning
# todo delete temp file or found how not to create it
def add_new_result(menu, people, hash_key):
    prediction_file = make_prediction_file(menu, people, hash_key)
    result = Result(key_hash=hash_key, menu=menu, people=people,
                    generation_time=datetime.now(), prediction=prediction_file)
    result.save(force_insert=True)


# todo add csv and pandas in parsing
def read_menu_file(menu_file):
    menu_data = b''
    for chunk in menu_file.chunks():
        menu_data += chunk
    return menu_data


# todo add csv and pandas in parsing
def read_people_file(people_file):
    people_data = b''
    for chunk in people_file.chunks():
        people_data += chunk
    return people_data

