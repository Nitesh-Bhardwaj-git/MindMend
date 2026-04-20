from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from ..models import ForumPost, ForumReply
from ..forms import ForumPostForm, ForumReplyForm


def forum_list(request):
    category = request.GET.get('category', '')
    sort = request.GET.get('sort', 'newest')

    query = ForumPost.objects.annotate(reply_count=Count('forumreply'))
    if category:
        query = query.filter(category=category)

    if sort == 'popular':
        query = query.order_by('-reply_count', '-created_at')
    else:
        query = query.order_by('-created_at')

    paginator = Paginator(query, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'Mind_Mend/forum/forum_list.html', {
        'page_obj': page_obj,
        'posts': page_obj,
        'current_category': category,
        'current_sort': sort,
        'categories': ForumPost.CATEGORY_CHOICES,
    })

def recovery_stories(request):
    """Recovery stories routed through the unified forum list template."""
    posts = ForumPost.objects.filter(category='recovery').annotate(reply_count=Count('forumreply')).order_by('-created_at')
    paginator = Paginator(posts, 10)
    page = request.GET.get('page', 1)
    posts = paginator.get_page(page)
    return render(request, 'Mind_Mend/forum/forum_list.html', {'posts': posts, 'current_category': 'recovery'})

@login_required
def forum_create(request):
    if request.method == 'POST':
        form = ForumPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, 'Your post was created anonymously.')
            return redirect('forum_detail', pk=post.pk)
    else:
        form = ForumPostForm(initial={'is_anonymous': True})
    return render(request, 'Mind_Mend/forum/forum_create.html', {'form': form})


def forum_detail(request, pk):
    post = get_object_or_404(ForumPost.objects.annotate(reply_count=Count('forumreply')), pk=pk)
    replies = ForumReply.objects.filter(post=post).order_by('created_at')
    form = ForumReplyForm(initial={'is_anonymous': True}) if request.user.is_authenticated else None
    return render(request, 'Mind_Mend/forum/forum_detail.html', {
        'post': post,
        'replies': replies,
        'form': form,
    })


@login_required
def forum_reply(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if request.method == 'POST':
        form = ForumReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.post = post
            reply.author = request.user
            reply.save()
            messages.success(request, 'Reply posted successfully.')
    return redirect('forum_detail', pk=pk)
