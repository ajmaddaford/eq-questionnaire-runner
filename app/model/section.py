class Section(object):
    def __init__(self):
        self.id = None
        self.title = None
        self.questions = []

    def add_question(self, question):
        if question not in self.questions:
            self.questions.append(question)