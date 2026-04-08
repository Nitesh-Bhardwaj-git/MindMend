import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ..models import AssessmentResult
from ..forms import make_assessment_form
from ..assessment_data import (
    PHQ9_QUESTIONS, GAD7_QUESTIONS, PSS_QUESTIONS,
    get_phq9_result, get_gad7_result, get_pss_result, PSS_REVERSE_ITEMS
)

ASSESSMENT_SCALE_LABELS = ['Not at all', 'Several days', 'More than half', 'Nearly every day']


def build_assessment_context(form, title, heading, intro, questions, scale_max=3, scale_labels=None, input_prefix='assessment'):
    if scale_labels is None:
        scale_labels = ASSESSMENT_SCALE_LABELS
    options = [(i, f"{i} - {scale_labels[i] if i < len(scale_labels) else ''}") for i in range(scale_max + 1)]
    return {
        'form': form,
        'title': title,
        'assessment_title': title,
        'assessment_heading': heading,
        'assessment_intro': intro,
        'questions': questions,
        'options': options,
        'input_prefix': input_prefix,
    }


def build_combined_result(last_results):
    max_scores = {'phq9': 27, 'gad7': 21, 'pss': 40}
    if not all(last_results.get(name) for name in ('phq9', 'gad7', 'pss')):
        return None

    items = []
    total_percent = 0
    for name, label in [('phq9', 'PHQ-9'), ('gad7', 'GAD-7'), ('pss', 'PSS-10')]:
        result = last_results[name]
        max_score = max_scores[name]
        percent = (result.total_score / max_score) * 100 if max_score else 0
        items.append({
            'name': label,
            'level': result.result_level,
            'score': result.total_score,
            'max_score': max_score,
            'percent': percent,
            'date': result.created_at,
        })
        total_percent += percent

    average_percent = total_percent / len(items)
    if average_percent < 33:
        summary_title = 'Low overall concern'
        summary_text = 'Your most recent assessments indicate a generally low combined level of depression, anxiety, and stress.'
        tips = [
            '✓ Continue your current healthy habits and routines.',
            '✓ Maintain regular physical activity and adequate sleep.',
            '✓ Stay connected with supportive friends and family.',
            '✓ Regularly check in with yourself through assessments.',
        ]
    elif average_percent < 66:
        summary_title = 'Moderate overall concern'
        summary_text = 'Your most recent assessments indicate a moderate combined level of mental health symptoms. Consider self-care and monitoring your wellbeing.'
        tips = [
            '💡 Practice stress-reduction techniques like meditation or deep breathing.',
            '💡 Maintain a consistent sleep schedule and limit caffeine.',
            '💡 Engage in physical activity for at least 30 minutes daily.',
            '💡 Consider talking to a counselor or therapist for professional support.',
            '💡 Track your mood and triggers to identify patterns.',
        ]
    else:
        summary_title = 'High overall concern'
        summary_text = 'Your most recent assessments indicate a higher combined level of depression, anxiety, and stress. Consider seeking professional support.'
        tips = [
            '🔔 Reach out to a mental health professional immediately.',
            '🔔 Call a crisis helpline if you\'re in distress (KIRAN: 1800-599-0019).',
            '🔔 Establish a daily routine with regular sleep, meals, and exercise.',
            '🔔 Minimize stress by setting boundaries and delegating tasks.',
            '🔔 Connect with supportive people and share what you\'re experiencing.',
            '🔔 Avoid alcohol and drugs, which can worsen symptoms.',
        ]

    return {
        'average_percent': average_percent,
        'summary_title': summary_title,
        'summary_text': summary_text,
        'items': items,
        'tips': tips,
    }


@login_required
def assessments_home(request):
    last_results = {
        'phq9': None,
        'gad7': None,
        'pss': None,
    }
    if request.user.is_authenticated:
        last_results = {
            'phq9': AssessmentResult.objects.filter(user=request.user, assessment_type='phq9').order_by('-created_at').first(),
            'gad7': AssessmentResult.objects.filter(user=request.user, assessment_type='gad7').order_by('-created_at').first(),
            'pss': AssessmentResult.objects.filter(user=request.user, assessment_type='pss').order_by('-created_at').first(),
        }
    combined_result = build_combined_result(last_results)
    return render(request, 'Mind_Mend/assessments.html', {
        'last_results': last_results,
        'combined_result': combined_result,
    })


def _process_phq9(request, form_class):
    form = form_class(request.POST)
    if form.is_valid():
        scores = [form.cleaned_data[f'q{i}'] for i in range(len(PHQ9_QUESTIONS))]
        total = sum(scores)
        level = get_phq9_result(total)
        result = AssessmentResult.objects.create(
            user=request.user,
            assessment_type='phq9',
            total_score=total,
            result_level=level,
            answers=form.cleaned_data
        )
        return redirect('assessment_result', result_id=result.id)
    return render(request, 'Mind_Mend/assessment_form.html', build_assessment_context(
        form,
        title='PHQ-9 (Depression Assessment)',
        heading='PHQ-9 (Depression Assessment)',
        intro='Over the last 2 weeks, how often have you been bothered by any of the following problems?',
        questions=PHQ9_QUESTIONS,
        scale_max=3,
        input_prefix='phq9'
    ))


@login_required
def assessment_phq9(request):
    PHQ9Form = make_assessment_form(PHQ9_QUESTIONS)
    if request.method == 'POST':
        return _process_phq9(request, PHQ9Form)
    return render(request, 'Mind_Mend/assessment_form.html', build_assessment_context(
        PHQ9Form(),
        title='PHQ-9 (Depression Assessment)',
        heading='PHQ-9 (Depression Assessment)',
        intro='Over the last 2 weeks, how often have you been bothered by any of the following problems?',
        questions=PHQ9_QUESTIONS,
        scale_max=3,
        input_prefix='phq9'
    ))


def _process_gad7(request, form_class):
    form = form_class(request.POST)
    if form.is_valid():
        scores = [form.cleaned_data[f'q{i}'] for i in range(len(GAD7_QUESTIONS))]
        total = sum(scores)
        level = get_gad7_result(total)
        result = AssessmentResult.objects.create(
            user=request.user,
            assessment_type='gad7',
            total_score=total,
            result_level=level,
            answers=form.cleaned_data
        )
        return redirect('assessment_result', result_id=result.id)
    return render(request, 'Mind_Mend/assessment_form.html', build_assessment_context(
        form,
        title='GAD-7 (Anxiety Assessment)',
        heading='GAD-7 (Anxiety Assessment)',
        intro='Over the last 2 weeks, how often have you been bothered by the following problems?',
        questions=GAD7_QUESTIONS,
        scale_max=3,
        input_prefix='gad7'
    ))


@login_required
def assessment_gad7(request):
    GAD7Form = make_assessment_form(GAD7_QUESTIONS)
    if request.method == 'POST':
        return _process_gad7(request, GAD7Form)
    return render(request, 'Mind_Mend/assessment_form.html', build_assessment_context(
        GAD7Form(),
        title='GAD-7 (Anxiety Assessment)',
        heading='GAD-7 (Anxiety Assessment)',
        intro='Over the last 2 weeks, how often have you been bothered by the following problems?',
        questions=GAD7_QUESTIONS,
        scale_max=3,
        input_prefix='gad7'
    ))


def _process_pss(request, form_class):
    form = form_class(request.POST)
    if form.is_valid():
        raw_scores = [form.cleaned_data[f'q{i}'] for i in range(len(PSS_QUESTIONS))]
        total = sum((4 - score) if (i + 1) in PSS_REVERSE_ITEMS else score for i, score in enumerate(raw_scores))
        level = get_pss_result(raw_scores)
        result = AssessmentResult.objects.create(
            user=request.user,
            assessment_type='pss',
            total_score=total,
            result_level=level,
            answers=form.cleaned_data
        )
        return redirect('assessment_result', result_id=result.id)
    scale_labels = ['Never', 'Almost Never', 'Sometimes', 'Fairly Often', 'Very Often']
    return render(request, 'Mind_Mend/assessment_form.html', build_assessment_context(
        form,
        title='PSS-10 (Perceived Stress Scale)',
        heading='PSS-10 (Perceived Stress Scale)',
        intro='In the last month, how often have you felt or thought a certain way?',
        questions=PSS_QUESTIONS,
        scale_max=4,
        scale_labels=scale_labels,
        input_prefix='pss'
    ))


@login_required
def assessment_pss(request):
    scale_labels = ['Never', 'Almost Never', 'Sometimes', 'Fairly Often', 'Very Often']
    PSSForm = make_assessment_form(PSS_QUESTIONS, scale_max=4, scale_labels=scale_labels)
    if request.method == 'POST':
        return _process_pss(request, PSSForm)
    return render(request, 'Mind_Mend/assessment_form.html', build_assessment_context(
        PSSForm(),
        title='PSS-10 (Perceived Stress Scale)',
        heading='PSS-10 (Perceived Stress Scale)',
        intro='In the last month, how often have you felt or thought a certain way?',
        questions=PSS_QUESTIONS,
        scale_max=4,
        scale_labels=scale_labels,
        input_prefix='pss'
    ))


@login_required
def assessment_result(request, result_id):
    result = get_object_or_404(AssessmentResult, id=result_id, user=request.user)
    max_scores = {'phq9': 27, 'gad7': 21, 'pss': 40}
    assessment_names = {'phq9': 'PHQ-9', 'gad7': 'GAD-7', 'pss': 'PSS-10'}
    max_score = max_scores.get(result.assessment_type, 100)
    percent = (result.total_score / max_score) * 100 if max_score > 0 else 0

    return render(request, 'Mind_Mend/assessment_result.html', {
        'result': result,
        'assessment_name': assessment_names.get(result.assessment_type, 'Assessment'),
        'score': result.total_score,
        'result_level': result.result_level,
        'max_score': max_score,
        'percent': min(percent, 100),
        'next_url': reverse('assessments'),
    })
