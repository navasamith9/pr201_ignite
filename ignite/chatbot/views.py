import json
import random
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import QuestionFrequency
from .rag_engine import rag_engine

DEFAULT_QUESTIONS = [
    "What is the minimum CPI requirement for graduation at IIITDMJ?",
    "How does the branch change process work for B.Tech students?",
    "What are the undergraduate programmes offered by IIITDMJ?",
    "What is the attendance requirement policy for IIITDMJ courses?",
    "What hostellers and campus facilities are available at IIITDMJ?"
]

def get_dynamic_suggestions():
    # Retrieve question frequencies from DB
    freq_qs = list(QuestionFrequency.objects.order_by('-count', '-updated_at')[:10])
    f_count = len(freq_qs)
    
    selected_suggestions = []
    
    if f_count == 0:
        # 0 frequent -> 3 random defaults
        selected_suggestions = random.sample(DEFAULT_QUESTIONS, k=min(3, len(DEFAULT_QUESTIONS)))
    elif f_count == 1:
        # 1 frequent -> 1 freq + 2 random
        selected_suggestions.append(freq_qs[0].query_text)
        rem_defaults = [q for q in DEFAULT_QUESTIONS if q != freq_qs[0].query_text]
        selected_suggestions.extend(random.sample(rem_defaults, k=min(2, len(rem_defaults))))
    elif f_count == 2:
        # 2 frequent -> 2 freq + 1 random
        selected_suggestions.extend([q.query_text for q in freq_qs[:2]])
        rem_defaults = [q for q in DEFAULT_QUESTIONS if q not in selected_suggestions]
        selected_suggestions.extend(random.sample(rem_defaults, k=min(1, len(rem_defaults))))
    else:
        # 3 or more frequent -> top 3 frequent / latest
        selected_suggestions = [q.query_text for q in freq_qs[:3]]

    return selected_suggestions

def chatbot_home(request):
    initial_suggestions = get_dynamic_suggestions()
    return render(request, 'chatbot/index.html', {
        'initial_suggestions': initial_suggestions
    })

@csrf_exempt
def suggestions_api(request):
    suggestions = get_dynamic_suggestions()
    return JsonResponse({'suggestions': suggestions})

@csrf_exempt
def query_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
        
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
    except Exception:
        query = request.POST.get('query', '').strip()

    if not query:
        return JsonResponse({'error': 'Query cannot be empty'}, status=400)

    # Execute RAG query first
    result = rag_engine.answer_query(query)

    # Track question frequency ONLY if valid and IN-CONTEXT
    if result.get('in_context') and len(query) > 5 and len(query) < 400:
        obj, created = QuestionFrequency.objects.get_or_create(
            query_text=query,
            defaults={'count': 1}
        )
        if not created:
            obj.count += 1
            obj.save()
    
    # Get updated 3 dynamic suggestions
    new_suggestions = get_dynamic_suggestions()
    result['suggestions'] = new_suggestions
    
    return JsonResponse(result)
