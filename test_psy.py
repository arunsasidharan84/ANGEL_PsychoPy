from psychopy.experiment import Experiment
exp = Experiment()
exp.loadFromXML('angel_paradigm.psyexp')
exp.writeScript('test_out.py')
