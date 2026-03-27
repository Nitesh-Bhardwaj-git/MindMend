import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ..models import AssessmentResult
from ..forms import make_assessment_form
from ..assessment_data import (
    PHQ9_QUESTIONS, GAD7_QUESTIONS, PSS_QUESTIONS,
    get_phq9_result, get_gad7_result, get_pss_result, PSS_REVERSE_ITEMS
)

@login_required
def assessments_home(request):
    return render(request, 'Mind_Mend/assessments.html')


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
    return render(request, 'Mind_Mend/assessment_form.html', {
        'form': form, 'title': 'PHQ-9 (Depression Assessment)', 'type': 'phq9',
        'desc': 'Over the last 2 weeks, how often have you been bothered by any of the following problems?'
    })


@login_required
def assessment_phq9(request):
    PHQ9Form = make_assessment_form(PHQ9_QUESTIONS)
    if request.method == 'POST':
        return _process_phq9(request, PHQ9Form)
    return render(request, 'Mind_Mend/assessment_form.html', {
        'form': PHQ9Form(), 'title': 'PHQ-9 (Depression Assessment)', 'type': 'phq9',
        'desc': 'Over the last 2 weeks, how often have you been bothered by any of the following problems?'
    })


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
    return render(request, 'Mind_Mend/assessment_form.html', {
        'form': form, 'title': 'GAD-7 (Anxiety Assessment)', 'type': 'gad7',
        'desc': 'Over the last 2 weeks, how often have you been bothered by the following problems?'
    })


@login_required
def assessment_gad7(request):
    GAD7Form = make_assessment_form(GAD7_QUESTIONS)
    if request.method == 'POST':
        return _process_gad7(request, GAD7Form)
    return render(request, 'Mind_Mend/assessment_form.html', {
        'form': GAD7Form(), 'title': 'GAD-7 (Anxiety Assessment)', 'type': 'gad7',
        'desc': 'Over the last 2 weeks, how often have you been bothered by the following problems?'
    })


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
    return render(request, 'Mind_Mend/assessment_form.html', {
        'form': form, 'title': 'PSS-10 (Perceived Stress Scale)', 'type': 'pss',
        'desc': 'In the last month, how often have you felt or thought a certain way?'
    })


@login_required
def assessment_pss(request):
    scale_labels = ['Never', 'Almost Never', 'Sometimes', 'Fairly Often', 'Very Often']
    PSSForm = make_assessment_form(PSS_QUESTIONS, scale_max=4, scale_labels=scale_labels)
    if request.method == 'POST':
        return _process_pss(request, PSSForm)
    return render(request, 'Mind_Mend/assessment_form.html', {
        'form': PSSForm(), 'title': 'PSS-10 (Perceived Stress Scale)', 'type': 'pss',
        'desc': 'In the last month, how often have you felt or thought a certain way?'
    })


@login_required
def assessment_result(request, result_id):
    result = get_object_or_404(AssessmentResult, id=result_id, user=request.user)
    max_scores = {'phq9': 27, 'gad7': 21, 'pss': 40}
    max_score = max_scores.get(result.assessment_type, 100)
    percent = (result.total_score / max_score) * 100 if max_score > 0 else 0

    return render(request, 'Mind_Mend/assessment_result.html', {
        'result': result,
        'percent': min(percent, 100),
        'max_score': max_score
    })
