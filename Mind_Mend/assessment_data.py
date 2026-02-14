"""Assessment questionnaires: PHQ-9, GAD-7, PSS-10"""

PHQ9_QUESTIONS = [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself or that you are a failure",
    "Trouble concentrating on things",
    "Moving or speaking so slowly that others notice, or being fidgety/restless",
    "Thoughts that you would be better off dead or of hurting yourself",
]

PHQ9_SCORING = {
    (0, 4): "Minimal depression",
    (5, 9): "Mild depression",
    (10, 14): "Moderate depression",
    (15, 19): "Moderately severe depression",
    (20, 27): "Severe depression",
}

GAD7_QUESTIONS = [
    "Feeling nervous, anxious, or on edge",
    "Not being able to stop or control worrying",
    "Worrying too much about different things",
    "Trouble relaxing",
    "Being so restless that it's hard to sit still",
    "Becoming easily annoyed or irritable",
    "Feeling afraid as if something awful might happen",
]

GAD7_SCORING = {
    (0, 4): "Minimal anxiety",
    (5, 9): "Mild anxiety",
    (10, 14): "Moderate anxiety",
    (15, 21): "Severe anxiety",
}

PSS_QUESTIONS = [
    "How often have you been upset because of something that happened unexpectedly?",
    "How often have you felt unable to control important things in your life?",
    "How often have you felt nervous and stressed?",
    "How often have you felt confident about your ability to handle personal problems?",  # reverse
    "How often have you felt that things were going your way?",  # reverse
    "How often have you found you could not cope with all the things you had to do?",
    "How often have you been able to control irritations in your life?",  # reverse
    "How often have you felt on top of things?",  # reverse
    "How often have you been angered because of things outside your control?",
    "How often have you felt difficulties were piling up so high you could not overcome them?",
]

PSS_REVERSE_ITEMS = [4, 5, 7, 8]  # 1-indexed for clarity, convert to 0-index in code


def get_phq9_result(score):
    for (low, high), label in PHQ9_SCORING.items():
        if low <= score <= high:
            return label
    return "Unknown"


def get_gad7_result(score):
    for (low, high), label in GAD7_SCORING.items():
        if low <= score <= high:
            return label
    return "Unknown"


def get_pss_result(answers):
    """PSS-10: items 4,5,7,8 are reverse scored (4-x). Total 0-40."""
    total = 0
    for i, ans in enumerate(answers):
        if (i + 1) in PSS_REVERSE_ITEMS:
            total += (4 - ans)
        else:
            total += ans
    if total <= 13:
        return "Low stress"
    elif total <= 26:
        return "Moderate stress"
    else:
        return "High stress"
