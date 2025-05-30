import logging
from bs4 import BeautifulSoup
from datetime import datetime
from xQuiz.quiz_manager import (
    QuizAnswerQueue,
    create_new_quiz_game,
    get_current_question,
    get_next_hint,
    update_user_score,
    get_quiz_scores,
    get_random_quiz_question,
    get_random_pro_wrestling_joke
)
from api_calls import post_forum_reply

logger = logging.getLogger(__name__)

class QuizHandler:
    def __init__(self):
        """Inicjalizacja handlera quizu."""
        self.answer_queue = QuizAnswerQueue()
        logger.info("Quiz handler initialized")

    def handle_quiz_topic_create(self, topic_id, content):
        """Obsługuje utworzenie nowego tematu quizu."""
        try:
            logger.info("Processing new quiz topic creation")
            
            # Sprawdzenie czy to jest post inicjujący quiz
            if "start quiz" not in content.lower():
                logger.debug("Not a quiz start post")
                return False

            # Utworzenie pierwszego pytania
            question_data = get_random_quiz_question()
            if not question_data:
                logger.error("Failed to generate quiz question")
                return False
            
            logger.info(f"Generated question data: {question_data}")
            if not question_data['answer']:
                logger.error("Generated question does not have an answer")
                return False
            
            category = "wrestling"  # Domyślna kategoria dla pierwszego pytania
            question_id = create_new_quiz_game(topic_id, question_data['question'], question_data['answer'], question_data['hints'], category)
            
            if not question_id:
                logger.error("Failed to create initial quiz question in the database")
                return False

            logger.info(f"Created new quiz question with ID: {question_id}")

            # Wysłanie pierwszej podpowiedzi
            initial_hint = get_next_hint(question_id, question_data['question'])
            if not initial_hint:
                logger.error("Failed to generate initial hint")
                return False

            response = f"""
            <p style="text-align: center;">
                <span style="font-size:22px;"><strong>Podpowiedź</strong></span><br>
                &nbsp;
            </p>
            {initial_hint}
            """

            logger.info(f"Posting initial hint to topic ID: {topic_id}")
            post_forum_reply(topic_id, response)
            logger.info(f"New quiz started - Question ID: {question_id}")
            return True

        except Exception as e:
            logger.error(f"Error handling quiz topic creation: {e}")
            return False

    def handle_quiz_post(self, topic_id, content, username, author_id):
        """
        Obsługuje post w temacie quizu.
        - Pobiera aktualne pytanie.
        - Sprawdza odpowiedź użytkownika.
        - Jeśli odpowiedź poprawna: nagradza, publikuje ranking, prosi o nową kategorię.
        - Jeśli niepoprawna: generuje podpowiedź przez xAI na bieżąco na podstawie wszystkich postów od zadania pytania.
        """
        from bs4 import BeautifulSoup
        from xQuiz.quiz_manager import (
            get_current_question,
            update_user_score,
            get_quiz_scores,
            get_next_hint,
            get_random_pro_wrestling_joke,
        )
        from api_calls import post_forum_reply

        logger = logging.getLogger(__name__)

        try:
            logger.info(f"Processing quiz post - User: {username}, Content: {content[:100]}")

            # Pobierz aktualne pytanie
            current_question = get_current_question(topic_id)
            if not current_question:
                logger.error(f"No active question found for topic {topic_id}")
                return False

            # Wyodrębnij odpowiedź użytkownika (czyści html)
            soup = BeautifulSoup(content, 'html.parser')
            guess = soup.get_text().strip()

            logger.debug(f"Quiz answer attempt - User: {username}, Guess: {guess}")

            # Sprawdź odpowiedź
            correct_answer = current_question.get('answer', '').lower().strip()
            user_answer = guess.lower().strip()
            variants = [
                v.lower().strip() for v in current_question.get('variants', '').split(',') if v
            ] if current_question.get('variants') else []

            if user_answer == correct_answer or user_answer in variants:
                logger.info(f"Correct answer from user {username}!")
                # Dodaj punkt
                update_user_score(username, 1)
                # Pobierz ranking
                scores = get_quiz_scores()
                score_table = """
                <style type="text/css">
                body { font-family: Arial, sans-serif; }
                table { max-width: calc(100% - 20px); border-collapse: collapse; margin-left: auto; margin-right: auto; }
                th, td { padding: 8px 10px; text-align: left; border: 1px solid black; }
                th { font-weight: bold; }
                </style>
                <table>
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Punkty</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                for i, score in enumerate(scores):
                    user = score['user_name']
                    pts = score['score']
                    if i == 0:
                        score_table += f'<tr><td><strong><span style="color:#e67e22;">{user}</span></strong></td><td>Liczba punktów {pts}</td></tr>'
                    elif i == 1:
                        score_table += f'<tr><td><strong><span style="color:#7f8c8d;">{user}</span></strong></td><td>Liczba punktów {pts}</td></tr>'
                    elif i == 2:
                        score_table += f'<tr><td><span style="color:#330000;"><strong>{user}</strong></span></td><td>Liczba punktów {pts}</td></tr>'
                    else:
                        score_table += f'<tr><td>{user}</td><td>Liczba punktów {pts}</td></tr>'
                score_table += "</tbody></table>"

                response = (
                    f"<p style='text-align: justify;'>"
                    f"Gratulacje {username}! Poprawna odpowiedź na pytanie dotyczyła \"{current_question['question']}\"."
                    f"</p>{score_table}"
                    f"<p style='text-align: justify;'><strong>Podaj kategorię następnego pytania!</strong><br>"
                    f"Możesz wybrać dowolną kategorię związaną z wrestlingiem, np.:<br>"
                    f"- Historia konkretnej federacji<br>"
                    f"- Biografia wybranego wrestlera<br>"
                    f"- Konkretna era wrestlingu<br>"
                    f"- Gale pay-per-view<br>"
                    f"- Stajnie i tag teamy<br>"
                    f"- i wiele innych!"
                    f"</p>"
                )
                post_forum_reply(topic_id, response)
                logger.info(f"Correct answer handled - User: {username}")
                return True
            else:
                logger.debug(f"Wrong answer from user {username}")

                # Dodaj zgłoszoną odpowiedź do kolejki (jeśli nadal chcesz logować próby odpowiedzi)
                if hasattr(self, "answer_queue"):
                    self.answer_queue.add_answer(current_question['id'], username, guess)

                # Wygeneruj aktualną podpowiedź przez xAI na podstawie postów od zadania pytania
                new_hint = get_next_hint(topic_id, current_question)
                if new_hint:
                    response = (
                        "<p style='text-align: center;'>"
                        "<span style='font-size:22px;'><strong>Podpowiedź</strong></span><br>&nbsp;</p>"
                        f"{new_hint}"
                    )
                    post_forum_reply(topic_id, response)
                else:
                    # Jeśli nie da się wygenerować podpowiedzi, opowiedz żart
                    joke = get_random_pro_wrestling_joke()
                    response = (
                        "<p style='text-align: justify;'>"
                        "Niestety nie udzieliłeś poprawnej odpowiedzi. Na pocieszenie opowiadam kawał:"
                        "</p>"
                        f"<p style='text-align: justify;'>{joke}&nbsp;"
                        "<img alt=':leo:' data-emoticon='true' loading='lazy' "
                        "src='https://forum.wrestling.pl/uploads/emoticons/leo.png' style='width: 40px; height: auto;' title=':leo:'>"
                        "</p>"
                    )
                    post_forum_reply(topic_id, response)
                return True

        except Exception as e:
            logger.error(f"Error handling quiz post: {e}")
            return False

    def _check_answer_similarity(self, user_answer, correct_answer, variants):
        """Sprawdza podobieństwo odpowiedzi."""
        logger.debug(f"Checking answer similarity:\nUser answer: {user_answer}\nCorrect answer: {correct_answer}\nVariants: {variants}")
        
        # Normalizacja odpowiedzi
        user_answer = user_answer.lower().strip()
        correct_answer = correct_answer.lower().strip()
        variants = [v.lower().strip() for v in variants if v]
        
        # Sprawdzenie dokładnego dopasowania
        if user_answer == correct_answer:
            return True
            
        # Sprawdzenie wariantów
        for variant in variants:
            if user_answer == variant:
                return True
                
        return False

    def _handle_correct_answer(self, topic_id, current_question, username):
        """Obsługuje poprawną odpowiedź."""
        try:
            # Dodaj 1 punkt za poprawną odpowiedź
            update_user_score(username, 1)

            # Pobierz aktualny ranking
            scores = get_quiz_scores()
            
            # Generuj tabelę wyników
            score_table = """
            <p>
                <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
            </p>
            <title>
            </title>
            <style type="text/css">
            body {
                font-family: Arial, sans-serif;
            }
            table {
                max-width: calc(100% - 20px);
                border-collapse: collapse;
                margin-left: auto;
                margin-right: auto;
            }
            th, td {
                padding: 8px 10px;
                text-align: left;
                border: 1px solid black;
            }
            th {
                font-weight: bold;
            }</style>
            <p>&nbsp;</p>
            <table>
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Punkty</th>
                    </tr>
                </thead>
                <tbody>
            """

            # Dodaj wszystkich użytkowników do tabeli
            for i, score in enumerate(scores):
                if i == 0:
                    score_table += f"""
                    <tr>
                        <td><strong><span style="color:#e67e22;">{score['user_name']}</span></strong></td>
                        <td>Liczba punktów {score['score']}</td>
                    </tr>
                    """
                elif i == 1:
                    score_table += f"""
                    <tr>
                        <td><strong><span style="color:#7f8c8d;">{score['user_name']}</span></strong></td>
                        <td>Liczba punktów {score['score']}</td>
                    </tr>
                    """
                elif i == 2:
                    score_table += f"""
                    <tr>
                        <td><span style="color:#330000;"><strong>{score['user_name']}</strong></span></td>
                        <td>Liczba punktów {score['score']}</td>
                    </tr>
                    """
                else:
                    score_table += f"""
                    <tr>
                        <td>{score['user_name']}</td>
                        <td>Liczba punktów {score['score']}</td>
                    </tr>
                    """

            score_table += """
                </tbody>
            </table>
            <p>&nbsp;</p>
            """
            # Wyślij gratulacje i poproś o podanie kategorii
            response = f"""
            <p style="text-align: justify;">
                Gratulacje {username}! Poprawna odpowiedź na pytanie dotyczyła "{current_question['question']}".
            </p>
            {score_table}
            <p style="text-align: justify;">
                <strong>Podaj kategorię następnego pytania!</strong><br>
                Możesz wybrać dowolną kategorię związaną z wrestlingiem, np.:<br>
                - Historia konkretnej federacji<br>
                - Biografia wybranego wrestlera<br>
                - Konkretna era wrestlingu<br>
                - Gale pay-per-view<br>
                - Stajnie i tag teamy<br>
                - i wiele innych!
            </p>
            """

            post_forum_reply(topic_id, response)
            logger.info(f"Correct answer handled - User: {username}")
            return True

        except Exception as e:
            logger.error(f"Error handling correct answer: {e}")
            return False