import functools
from django.contrib.auth import authenticate, login
from mlalgorithms.shell import Shell
from re import compile
from os import path, mkdir, remove
from json import loads
from time import sleep
from django.core.files import File
from django.contrib.auth.models import User, Group
from .models import AlgorithmSettings
from django.http import HttpResponseRedirect
from django.urls import reverse


prog = compile(r"^[-0-9\w\s.@]+$")


def generate_model(package, algorithm, user_id):
    """
    Function for creating new model source.

    :param package: str
        Name of package.

    :param algorithm: str
        Name of algorithm.

    :param user_id: User
        Unique id for file.

    """
    if not path.exists('models'):
        mkdir('models')
    file = open('models/' + str(user_id) + '.py', 'w+')
    file.write(f'''
import numpy as np

from sklearn.{package} import {algorithm}

from mlalgorithms.models import model


class user_model(model.IModel):

    def __init__(self, **kwargs):
        self.model = {algorithm}(**kwargs)

    def train(self, train_samples, train_labels, **kwargs):
        self.model.fit(train_samples, train_labels, **kwargs)

    def predict(self, samples, **kwargs):
        predicts = []
        for sample in samples:
            prediction = self.model.predict(np.array(sample).reshape(1, -1))[0]
            predicts.append(prediction)
        return predicts


''')
    file.close()


def make_train(train_data, alg_settings):
    """
    Function for train new model.

    :param train_data: File
        Data for train

    :param alg_settings: AlgorithmSettings
        Model of user settings

    :return: str
        Description of resulted model.
    """
    generate_model(alg_settings.algorithm_package, alg_settings.algorithm_name,
                   alg_settings.user)
    params = {
        "selected_model": "user_model",
        "models": [
            {
                "model_module_name": "models." + str(alg_settings.user),
                "model_name": "user_model",

                "model_params": loads(alg_settings.algorithm_settings)
            }
        ],
        "selected_parser": "CommonParser",
        "parsers": [
            {
                "parser_module_name": "mlalgorithms.parsers.common_parser",
                "parser_name": "CommonParser",

                "parser_params": {
                    "proportion": alg_settings.parser_proportion,
                    "raw_date": alg_settings.parser_raw_date,
                    "n_rows": alg_settings.parser_rows
                }
            }
        ],
        "selected_metric": "f1",
        "metrics": {
            "mse": "MeanSquadError",
            "f1": "MeanF1Score"
        },

        "debug": alg_settings.with_debug
    }
    sh = Shell(existing_parsed_json_dict=params)
    sh.train(train_data)
    test_result, quality = sh.test()
    sh.save_model("models/" + str(alg_settings.user) + ".mdl")
    new_model = File(open("models/" + str(alg_settings.user) + ".mdl", "rb+"))
    alg_settings.model_file.delete()
    alg_settings.model_file = new_model
    alg_settings.save()
    new_model.close()
    if path.isfile("models/" + str(alg_settings.user) + ".mdl"):
        remove("models/" + str(alg_settings.user) + ".mdl")
    if path.isfile("models/" + str(alg_settings.user) + ".py"):
        remove("models/" + str(alg_settings.user) + ".py")
    return f'test_result: {test_result}\nquality: {quality}'


def make_prediction(input_data, menu_data, result_data, model_name):
    """
    Function for make prediction on trained model.

    :param input_data: File
        Test data for getting prediction.

    :param menu_data: File
        Menu data for prediction.

    :param result_data: File
        Result of prediction in needed format.

    :param model_name: File
        Path to model.
    """

    sh = Shell(existing_model_name=str(model_name))
    sh.predict(input_data, menu_data)
    sh.output(result_data)


def is_correct_string(line):
    """
    Function for checking correction of string

    :param line: str
        String for checking.

    :return: Boolean
        True if correct string False otherwise.
    """
    if type(line) != str:
        return False
    try:
        line.encode()
    except Exception:
        return False
    return len(line) > 0 and prog.match(line)


def check_content(necessary_fields, have_fields, exist_context={},
                  max_len=32):
    """
    Function for checking dict on contenting all necessary fields.

    :param necessary_fields: Tuple
        Fields which must contain have_fields.

    :param have_fields: Dict
        Dict with fields we have.

    :param exist_context: Dict
        Context which was added in template context before this function.

    :param max_len: Int
        Max len of string in input.

    :return: Boolean
        True if all ok False otherwise.
    """
    correct = True

    for field in necessary_fields:
        if field not in have_fields:
            correct = False
            exist_context['no_' + field] = True
        else:
            if type(have_fields[field]) == str:
                    if len(have_fields[field]) == 0:
                        correct = False
                        exist_context['no_' + field] = True
                    if not is_correct_string(have_fields[field]) or \
                            not len(have_fields[field]) < max_len:
                        correct = False
                        exist_context['incorrect_' + field] = True

    return correct


# TODO(Danila): change to more valid check
def is_email(email):
    """
    Function for validation users email.

    :param email: str
        String for checking if it is email.

    :return: Boolean
        True if it is correct email, False otherwise.
    """
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def authorise_user(request, context):
    """
    Function for processing users signing in.

    :param request: HttpRequest
        Http request for processing.

    :param context: Dict
        Existing context for page template.

    :return: Boolean
        True if user was authorised.
    """
    necessary_fields = ('username', 'password')
    no_error_context = check_content(necessary_fields, request.POST,
                                     context)
    if no_error_context:
        # Checking user details.
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return True
        else:
            context['incorrect_username_or_password'] = True
    return False


def register_user(request, context, form_fields):
    """
    Function for registration new user in system, saving information on
    registration page and signing in registered user.

    :param request: HttpRequest
        Http request for registration.

    :param context: Dict
        Existing context.

    :param form_fields: Tuple
        Fields for being saved in session.

    :return: Boolean
        True if user was registered, False otherwise.
    """

    for field in form_fields:
        if field in request.POST:
            request.session[field] = request.POST[field]

    # Check necessary fields.
    necessary_fields = ('first_name', 'last_name', 'email', 'password',
                        'login', 'password_double',)
    long_fields = ('question', 'answer')
    no_error_context = check_content(necessary_fields, request.POST,
                                     context)
    no_error_context = check_content(long_fields, request.POST, context, 128) \
                       and no_error_context

    # Check main fields
    if no_error_context:
        if User.objects.filter(username=request.POST['login']):
            context['incorrect_login'] = True
            no_error_context = False

        if not is_email(request.POST['email']) or \
                User.objects.filter(email=request.POST['email']):
            context['incorrect_email'] = True
            no_error_context = False

        if request.POST['password'] != request.POST['password_double']:
            context['not_match_passwords'] = True
            no_error_context = False

    if not no_error_context:
        return False

    # Check necessary fields.
    user = crete_user_with_settings(request.POST)

    login(request, user)

    return True


def fill_context(request, context, form_fields):
    """
    Function for filling context with form_fields with values from session if
     they in session.

    :param request: HttpRequest
        Http request with session.

    :param context: Dict
        Existing context.

    :param form_fields: Tuple
        Fields for checking.
    """
    for field in form_fields:
        if field in request.session:
            context[field] = request.session[field]


def decor_signed_in_to_next(func):
    """
    A decorator that checks if session had already authored user.

    :param func: function
        Function to decorate.

    :return function
        Decorated function.
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            if 'next' in request.GET:
                return HttpResponseRedirect(request.GET['next'])
            elif 'next' in request.POST:
                return HttpResponseRedirect(request.POST['next'])
            else:
                return HttpResponseRedirect(reverse('predictor:index'))

        result = func(request, *args, **kwargs)
        return result
    return wrapper


def crete_user_with_settings(user_description):
    """
    Function for creating user.

    :param user_description: Dict
        Correct dict with all information for creating user.

    :return: user
        Instance of new User.
    """
    user = User.objects.create_user(user_description['login'],
                                    user_description['email'],
                                    user_description['password'],
                                    first_name=user_description['first_name'],
                                    last_name=user_description['last_name'])

    # TODO(Danila): check if it need
    while True:
        try:
            default_model = File(open('models/default.mdl', 'rb+'))
            break
        except Exception:
            sleep(0.5)
    user_settings = AlgorithmSettings(user=user,
                                      question=user_description['question'],
                                      answer=user_description['answer'],
                                      model_file=default_model)
    user_settings.save()
    default_model.close()

    if 'is_researcher' in user_description:
        group = Group.objects.get_or_create(name='researcher')
        user.groups.add(group[0])
        user.save()

    return user


def restore_search_email(request, context):
    """
    Function for checking email in restore page, and setting next step if it is
    correct.

    :param request: HttpRequest
        Http request with session.

    :param context: Dict
        Existing context.
    """
    necessary_fields = ('email',)
    no_error_context = check_content(necessary_fields, request.POST,
                                     context)
    if no_error_context:
        users = User.objects.filter(email=request.POST['email'])
        if len(users) != 1:
            context['incorrect_email'] = True
        else:
            request.session['user_email'] = request.POST['email']
            request.session['confirmed'] = False


def restore_check_answer(request, context):
    """
    Function for checking secret answer in restore page, and setting next step
    if it is correct.

    :param request: HttpRequest
        Http request with session.

    :param context: Dict
        Existing context.
    """
    necessary_fields = ('answer',)
    no_error_context = check_content(necessary_fields, request.POST,
                                     context, 128)
    if no_error_context:
        users = User.objects.get(email=request.session['user_email'])
        answer = AlgorithmSettings.objects.get(user=users).answer
        if answer != request.POST['answer']:
            context['incorrect_answer'] = True
        else:
            request.session['confirmed'] = True


def restore_change_password(request, context):
    """
    Function for checking passwords, and changing user password if they are
    correct.

    :param request: HttpRequest
        Http request with session.

    :param context: Dict
        Existing context.

    :return Boolean
        True if password was changed, False otherwise.
    """
    necessary_fields = ('password', 'password_double')
    no_error_context = check_content(necessary_fields, request.POST,
                                     context)
    if no_error_context:
        if request.POST['password'] != request.POST['password_double']:
            context['not_match_password'] = True
            return False
        else:
            user = User.objects.filter(email=
                                       request.session['user_email'])[0]
            user.set_password(request.POST['password'])
            user.save()
            return True
    return False


def research_fill_data(request, context):
    if 'user_email' in request.session:
        if 'confirmed' not in request.session or\
                not request.session['confirmed']:
            users = User.objects.filter(email=
                                        request.session['user_email'])
            question = AlgorithmSettings.objects.filter(user=
                                                        users[0])[0].question
            context['secret_question'] = question
        else:
            context['confirmed'] = True
        context['email'] = request.session['user_email']
