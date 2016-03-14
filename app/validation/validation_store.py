from flask import session
from abc import ABCMeta, abstractmethod
from app.validation.validation_result import ValidationResult

RESULTS = 'val'


class ValidationStoreFactory(object):
    @staticmethod
    def create_validation_store():
        return FlaskValidationStore()


class IValidationStore(metaclass=ABCMeta):
    # keys are in the format...
    # group:block:section:question:response:<repetition>
    @abstractmethod
    def store_result(self, key, value):
        raise NotImplementedError()

    @abstractmethod
    def get_result(self, key):
        raise NotImplementedError()


class FlaskValidationStore(IValidationStore):

    def store_result(self, key, value):
        if RESULTS not in session:
            responses = {key: value.to_dict()}
            session[RESULTS] = responses
        else:
            session[RESULTS][key] = value.to_dict()
        session.permanent = True

    def get_result(self, key):
        if key in session[RESULTS].keys():
            result = ValidationResult()
            result.from_dict(session[RESULTS][key])
            return result
        return None


class MockValidationStore(IValidationStore):
    def __init__(self):
        self._store = {}

    def store_result(self, key, value):
        self._store[key] = value

    def get_result(self, key):
        return self._store[key] or None
