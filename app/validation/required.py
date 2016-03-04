from abstract_validator import AbstractValidator
from validation_result import ValidationResult


class Required(AbstractValidator):

    def validate(self):
      return ValidationResult()
