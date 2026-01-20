from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModel
import torch
import torch.nn.functional as F
import numpy as np

class FinBERTAnalyzer:
    """Production-ready FinBERT analysis system with advanced stress detection"""
    
    def __init__(self):
        print("Loading FinBERT models...")
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.sentiment_model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        self.embedding_model = AutoModel.from_pretrained("ProsusAI/finbert")
        
        # Move to GPU if available
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.sentiment_model.to(self.device)
        self.embedding_model.to(self.device)
        
        # Comprehensive stress keyword patterns with severity weights
        self.stress_keywords = {
            # High severity - Crisis level (0.85-0.95)
            'bankruptcy': 0.95, 'bankrupt': 0.95, 'foreclosure': 0.95,
            'eviction': 0.95, 'evicted': 0.95, 'repossession': 0.95,
            'defaulted': 0.90, 'default': 0.85, 'collections': 0.90,
            'collector': 0.85, 'lawsuit': 0.90, 'sued': 0.90,
            'garnished': 0.95, 'garnishment': 0.95, 'judgment': 0.85,
            'desperate': 0.90, 'hopeless': 0.90, 'drowning': 0.90,
            'overwhelmed': 0.85, 'crisis': 0.90, 'emergency': 0.85,
            'can\'t afford': 0.90, 'cannot afford': 0.90, 'broke': 0.85,
            'unpaid': 0.85, 'overdue': 0.90, 'delinquent': 0.90,
            'behind on': 0.85, 'missed payment': 0.85, 'late payment': 0.80,
            
            # Medium-high severity - Serious concern (0.70-0.84)
            'struggling': 0.85, 'struggle': 0.82, 'stressed': 0.80,
            'anxious': 0.75, 'anxiety': 0.75, 'panic': 0.80,
            'worried': 0.70, 'worry': 0.70, 'worrying': 0.72,
            'fear': 0.75, 'afraid': 0.75, 'scared': 0.78,
            'layoff': 0.85, 'laid off': 0.85, 'fired': 0.85,
            'unemployed': 0.85, 'unemployment': 0.85, 'jobless': 0.85,
            'redundancy': 0.82, 'cutback': 0.78, 'furlough': 0.80,
            'overdraft': 0.75, 'bounced': 0.80, 'declined': 0.75,
            'rejected': 0.78, 'denied': 0.78, 'insufficient funds': 0.82,
            'maxed out': 0.80, 'credit limit': 0.72, 'overlimit': 0.82,
            'losing': 0.75, 'failing': 0.78, 'sinking': 0.80,
            'trouble': 0.75, 'difficult': 0.70, 'difficulty': 0.72,
            'burden': 0.75, 'overwhelming': 0.78, 'unaffordable': 0.80,
            'expensive': 0.65, 'costly': 0.65, 'high cost': 0.68,
            
            # Medium severity - Elevated stress (0.55-0.69)
            'debt': 0.60, 'debts': 0.62, 'indebted': 0.68,
            'owe': 0.60, 'owing': 0.62, 'loan': 0.55,
            'borrow': 0.58, 'borrowing': 0.60, 'borrowed': 0.62,
            'concern': 0.60, 'concerned': 0.62, 'concerning': 0.65,
            'uncertain': 0.65, 'uncertainty': 0.68, 'unsure': 0.62,
            'confused': 0.60, 'confusing': 0.62, 'unclear': 0.60,
            'nervous': 0.65, 'uncomfortable': 0.63, 'uneasy': 0.65,
            'tight': 0.68, 'stretched': 0.70, 'squeezed': 0.68,
            'limited': 0.60, 'shortage': 0.70, 'short': 0.65,
            'irregular income': 0.80, 'unstable income': 0.78, 'variable income': 0.70,
            'inconsistent': 0.68, 'unpredictable': 0.72, 'volatile': 0.70,
            'bills': 0.58, 'expenses': 0.55, 'payments': 0.58,
            'installment': 0.60, 'installments': 0.60, 'monthly payment': 0.58,
            'interest': 0.55, 'high interest': 0.68, 'interest rate': 0.58,
            'penalty': 0.70, 'fee': 0.60, 'fees': 0.62, 'charge': 0.58,
            'minimum payment': 0.65, 'balance': 0.55, 'statement': 0.52,
            
            # Life events affecting finances (0.65-0.80)
            'divorce': 0.75, 'separated': 0.72, 'separation': 0.72,
            'medical': 0.70, 'hospital': 0.72, 'surgery': 0.75,
            'illness': 0.75, 'sick': 0.68, 'health': 0.60,
            'accident': 0.75, 'emergency room': 0.78, 'prescription': 0.62,
            'funeral': 0.80, 'death': 0.75, 'deceased': 0.75,
            'repair': 0.65, 'broken': 0.68, 'replacement': 0.65,
            'car broke': 0.72, 'appliance': 0.60, 'roof': 0.70,
            
            # Employment concerns (0.60-0.80)
            'reduced hours': 0.75, 'pay cut': 0.80, 'salary cut': 0.80,
            'part-time': 0.62, 'gig work': 0.68, 'freelance': 0.65,
            'contractor': 0.60, 'self-employed': 0.62, 'commission': 0.65,
            'seasonal': 0.70, 'temporary': 0.68, 'contract': 0.58,
            
            # Behavioral/emotional indicators (0.60-0.85)
            'sleepless': 0.80, 'can\'t sleep': 0.78, 'insomnia': 0.75,
            'depressed': 0.80, 'depression': 0.78, 'sad': 0.65,
            'frustrated': 0.68, 'frustration': 0.68, 'angry': 0.70,
            'ashamed': 0.75, 'embarrassed': 0.72, 'guilty': 0.70,
            'exhausted': 0.72, 'tired': 0.62, 'drained': 0.72,
            'trapped': 0.82, 'stuck': 0.75, 'cornered': 0.80,
            'helpless': 0.85, 'powerless': 0.82, 'out of control': 0.85,
            
            # Avoidance behaviors (0.70-0.85)
            'ignoring': 0.75, 'avoiding': 0.78, 'hiding': 0.80,
            'can\'t open': 0.82, 'unopened': 0.78, 'ignored': 0.75,
            'don\'t want to look': 0.80, 'afraid to check': 0.82,
            
            # Comparative stress (0.60-0.75)
            'worse': 0.70, 'worsening': 0.72, 'deteriorating': 0.75,
            'declining': 0.70, 'falling behind': 0.80, 'can\'t keep up': 0.78,
            'barely': 0.72, 'hardly': 0.70, 'just enough': 0.65,
            'not enough': 0.75, 'insufficient': 0.72, 'running out': 0.80,
            
            # Future anxiety (0.65-0.80)
            'never': 0.72, 'impossible': 0.75, 'won\'t be able': 0.78,
            'can\'t imagine': 0.70, 'no way': 0.75, 'no hope': 0.85,
            'retirement': 0.65, 'future': 0.58, 'savings': 0.55,
            'pension': 0.60, 'old age': 0.65,
        }
        
        print(f"✅ FinBERT loaded on {self.device}")
    
    def analyze_sentiment(self, text):
        """Analyze financial sentiment using FinBERT"""
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, 
                               truncation=True, max_length=512).to(self.device)
        
        with torch.no_grad():
            outputs = self.sentiment_model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        positive, negative, neutral = predictions[0].cpu().tolist()
        
        return {
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'dominant': max(['positive', 'negative', 'neutral'], 
                          key=lambda x: {'positive': positive, 'negative': negative, 'neutral': neutral}[x])
        }
    
    def detect_stress(self, text):
        """
        Advanced context-aware stress detection system
        
        Combines sentiment analysis with multi-dimensional keyword detection:
        - Multi-word stress phrases (highest priority)
        - Individual stress keywords (with diminishing returns)
        - Negation patterns (NOT worried, NO longer stressed)
        - Intensifiers (VERY, EXTREMELY, REALLY)
        - Mitigators (BUT improving, HOWEVER better)
        - Question vs statement differentiation
        
        Returns comprehensive stress analysis with transparency
        """
        
        text_lower = text.lower()
        
        # Step 1: Get base sentiment from FinBERT
        sentiment = self.analyze_sentiment(text)
        negative_score = sentiment['negative']
        
        # Step 2: Detect multi-word stress phrases (highest priority)
        phrase_stress, detected_phrases = self._detect_stress_phrases(text_lower)
        
        # Step 3: Detect individual keywords (avoid double-counting with phrases)
        keyword_stress, detected_keywords = self._detect_stress_keywords(text_lower, detected_phrases)
        
        # Step 4: Check for negation patterns
        negation_factor = self._detect_negation(text_lower, detected_keywords + detected_phrases)
        
        # Step 5: Check for intensifiers
        intensity_factor = self._detect_intensifiers(text_lower)
        
        # Step 6: Check for mitigating context
        mitigation_factor = self._detect_mitigators(text_lower)
        
        # Step 7: Check if it's a question (questions are less urgent)
        question_factor = 0.85 if '?' in text else 1.0
        
        # Step 8: Combine all factors with weights
        base_stress = (phrase_stress * 0.6 + keyword_stress * 0.4)
        adjusted_stress = base_stress * negation_factor * intensity_factor * mitigation_factor * question_factor
        
        # Step 9: Combine with FinBERT sentiment (50/50 weight)
        combined_stress = (0.5 * adjusted_stress + 0.5 * negative_score)
        combined_stress = min(combined_stress, 1.0)
        
        # Step 10: Classify stress level
        if combined_stress >= 0.75:
            stress_level = "HIGH"
            urgency = "Immediate response needed - High financial distress detected"
        elif combined_stress >= 0.55:
            stress_level = "MODERATE"
            urgency = "Active support recommended - Notable financial concern"
        elif combined_stress >= 0.35:
            stress_level = "LOW"
            urgency = "Monitor situation - Minor financial stress detected"
        else:
            stress_level = "MINIMAL"
            urgency = "No immediate intervention needed"
        
        # Step 11: Return comprehensive analysis
        return {
            'stress_level': stress_level,
            'urgency': urgency,
            'combined_score': combined_stress,
            'sentiment_score': negative_score,
            'keyword_score': keyword_stress,
            'phrase_score': phrase_stress,
            'detected_keywords': detected_keywords,
            'detected_phrases': detected_phrases,
            'context_adjustments': {
                'negation_factor': negation_factor,
                'intensity_factor': intensity_factor,
                'mitigation_factor': mitigation_factor,
                'question_factor': question_factor
            }
        }
    
    def _detect_stress_phrases(self, text):
        """
        Detect multi-word stress phrases that indicate specific financial distress
        These are weighted higher as they're more specific indicators
        """
        
        stress_phrases = {
            # Crisis phrases (0.85-0.95)
            'can\'t make ends meet': 0.90, 'cannot make ends meet': 0.90,
            'drowning in debt': 0.93, 'buried in debt': 0.90,
            'crushing debt': 0.92, 'mounting debt': 0.85, 'spiraling debt': 0.92,
            'living paycheck to paycheck': 0.85, 'paycheck to paycheck': 0.85,
            'barely scraping by': 0.88, 'barely getting by': 0.85,
            'can\'t keep up': 0.87, 'cannot keep up': 0.87,
            'falling further behind': 0.88, 'falling behind': 0.85,
            'running out of money': 0.90, 'run out of money': 0.90,
            'no money left': 0.92, 'out of money': 0.90,
            'at my wit\'s end': 0.87, 'at the end of my rope': 0.90,
            'don\'t know what to do': 0.82, 'no idea what to do': 0.82,
            'out of options': 0.88, 'no options left': 0.90,
            'choosing between': 0.85, 'either or': 0.82,
            'robbing peter to pay paul': 0.88, 'juggling bills': 0.83,
            
            # Employment crisis (0.80-0.90)
            'lost my job': 0.88, 'lost my income': 0.90, 'got laid off': 0.88,
            'been fired': 0.85, 'terminated from': 0.85,
            'unemployment running out': 0.90, 'benefits running out': 0.88,
            'hours cut': 0.80, 'hours reduced': 0.80,
            'pay cut': 0.85, 'salary reduced': 0.85,
            
            # Collections/legal (0.85-0.95)
            'collections calling': 0.90, 'debt collectors': 0.90,
            'creditors calling': 0.88, 'threatened with': 0.90,
            'facing foreclosure': 0.95, 'facing eviction': 0.95,
            'risk of losing': 0.88, 'about to lose': 0.90,
            'repo my car': 0.92, 'repossess my': 0.92,
            
            # Health/emergency (0.75-0.85)
            'medical emergency': 0.83, 'hospital bills': 0.80,
            'medical bills': 0.78, 'emergency surgery': 0.85,
            'unexpected medical': 0.80, 'car broke down': 0.77,
            'car died': 0.77, 'emergency repair': 0.80,
            
            # Avoidance behaviors (0.75-0.88)
            'afraid to open': 0.82, 'scared to check': 0.80,
            'can\'t even look': 0.83, 'don\'t want to know': 0.78,
            'ignoring the bills': 0.80, 'avoiding calls': 0.78,
            'hiding from': 0.82,
            
            # Moderate concern phrases (0.65-0.75)
            'tight budget': 0.70, 'budget is tight': 0.70,
            'money is tight': 0.72, 'running low': 0.73,
            'getting low': 0.70, 'not sure how': 0.68,
            'income varies': 0.72, 'income fluctuates': 0.73,
        }
        
        detected_phrases = []
        max_phrase_weight = 0
        
        for phrase, weight in stress_phrases.items():
            if phrase in text:
                detected_phrases.append(phrase)
                max_phrase_weight = max(max_phrase_weight, weight)
        
        # Multiple phrases = compounding stress
        if len(detected_phrases) > 1:
            phrase_stress = min(max_phrase_weight + (len(detected_phrases) - 1) * 0.05, 1.0)
        else:
            phrase_stress = max_phrase_weight
        
        return phrase_stress, detected_phrases
    
    def _detect_stress_keywords(self, text, detected_phrases):
        """
        Detect individual stress keywords with diminishing returns
        Avoids double-counting words already captured in phrases
        """
        
        detected_keywords = []
        keyword_weights = []
        
        # Extract words from detected phrases to avoid double-counting
        phrase_words = set()
        for phrase in detected_phrases:
            phrase_words.update(phrase.split())
        
        for keyword, weight in self.stress_keywords.items():
            # Only count if not already in a phrase
            if keyword in text and keyword not in phrase_words:
                detected_keywords.append(keyword)
                keyword_weights.append(weight)
        
        # Calculate with diminishing returns (prevents keyword stuffing)
        if keyword_weights:
            keyword_weights.sort(reverse=True)
            keyword_stress = 0
            
            # Each additional keyword contributes less (0.7^i factor)
            for i, weight in enumerate(keyword_weights[:5]):  # Cap at top 5
                keyword_stress += weight * (0.7 ** i)
            
            keyword_stress = min(keyword_stress, 1.0)
        else:
            keyword_stress = 0
        
        return keyword_stress, detected_keywords
    
    def _detect_negation(self, text, detected_terms):
        """
        Detect negation patterns that reduce stress
        e.g., "I'm NOT worried", "NO longer stressed"
        """
        
        negation_patterns = [
            'not ', 'no ', 'never ', 'nothing ', 'neither ', 'none ',
            'isn\'t ', 'aren\'t ', 'wasn\'t ', 'weren\'t ',
            'don\'t ', 'doesn\'t ', 'didn\'t ',
            'won\'t ', 'wouldn\'t ', 'can\'t ', 'couldn\'t ',
            'shouldn\'t ', 'no longer ', 'not anymore ',
            'without ', 'free from ', 'cleared ', 'resolved '
        ]
        
        negation_detected = False
        
        # Check if negation appears before any stress term
        for term in detected_terms:
            term_pos = text.find(term)
            if term_pos > 0:
                # Check 20 chars before the term for negation
                context = text[max(0, term_pos - 20):term_pos]
                for negation in negation_patterns:
                    if negation in context:
                        negation_detected = True
                        break
            if negation_detected:
                break
        
        # Significantly reduce stress if negation found
        return 0.4 if negation_detected else 1.0
    
    def _detect_intensifiers(self, text):
        """
        Detect intensifying words that increase stress severity
        e.g., "VERY worried", "EXTREMELY stressed"
        """
        
        intensifiers = {
            'very': 1.15, 'extremely': 1.25, 'really': 1.12,
            'seriously': 1.18, 'incredibly': 1.20, 'absolutely': 1.20,
            'completely': 1.22, 'totally': 1.18, 'utterly': 1.20,
            'severely': 1.25, 'desperately': 1.30,
            'constantly': 1.20, 'always': 1.15, 'continuously': 1.18,
            'increasingly': 1.15, 'progressively': 1.15,
            'getting worse': 1.20, 'much worse': 1.25, 'even more': 1.15,
        }
        
        max_intensity = 1.0
        for intensifier, factor in intensifiers.items():
            if intensifier in text:
                max_intensity = max(max_intensity, factor)
        
        return max_intensity
    
    def _detect_mitigators(self, text):
        """
        Detect mitigating words/phrases that reduce stress urgency
        e.g., "worried BUT improving", "stressed HOWEVER making progress"
        """
        
        mitigators = {
            'but ': 0.85, 'however ': 0.85, 'although ': 0.85,
            'though ': 0.87, 'yet ': 0.87,
            'improving': 0.80, 'better': 0.82, 'getting better': 0.78,
            'improving situation': 0.75, 'making progress': 0.80,
            'on track': 0.75, 'starting to': 0.85, 'beginning to': 0.85,
            'hope': 0.88, 'hopefully': 0.88, 'optimistic': 0.80,
            'confident': 0.82, 'plan to': 0.85, 'working on': 0.83,
            'trying to': 0.87, 'manageable': 0.80,
            'under control': 0.75, 'handling': 0.82, 'coping': 0.83,
        }
        
        min_mitigation = 1.0
        for mitigator, factor in mitigators.items():
            if mitigator in text:
                min_mitigation = min(min_mitigation, factor)
        
        return min_mitigation
    
    def get_embeddings(self, texts):
        """Generate FinBERT embeddings for RAG similarity search"""
        if isinstance(texts, str):
            texts = [texts]
        
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True,
                               truncation=True, max_length=512).to(self.device)
        
        with torch.no_grad():
            outputs = self.embedding_model(**inputs)
            embeddings = outputs.last_hidden_state[:, 0, :]
            embeddings = F.normalize(embeddings, p=2, dim=1)
        
        return embeddings.cpu().numpy()
    
    def find_similar_cases(self, query, top_k=3):
        """
        Find similar financial cases from knowledge base using RAG
        Returns top-k most similar cases with similarity scores
        """
        from data.case_database import get_case_database
        
        case_db = get_case_database()
        query_emb = self.get_embeddings(query)[0]
        
        case_texts = [case['description'] for case in case_db]
        case_embs = self.get_embeddings(case_texts)
        
        similarities = np.dot(case_embs, query_emb)
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            results.append({
                'case': case_db[idx],
                'similarity': float(similarities[idx])
            })
        
        return results