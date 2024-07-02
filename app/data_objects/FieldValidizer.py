class FieldValidizer:

    def _validize_fields(self):
        validations = getattr(self, f'_{self.__class__.__name__}__validations')
        validness = {self.__getattribute__(k): validations[k](self.__getattribute__(k)) for k in validations}
        invalid_fields = tuple(k for k, v in validness.items() if v is False)

        if invalid_fields:
            raise ValueError(f"Invaild field values: {', '.join(str(i) for i in invalid_fields)}")
