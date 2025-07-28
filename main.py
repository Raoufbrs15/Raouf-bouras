from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List
import os
import logging
from pathlib import Path

from database import get_db, init_db, Conversation

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modèles Pydantic pour les requêtes/réponses
class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="Question de l'utilisateur")

class ConversationResponse(BaseModel):
    id: int
    question: str
    reponse: str
    timestamp: str

    class Config:
        from_attributes = True

# Classe Agent - Logique du chatbot
class Agent:
    def __init__(self):
        self.nom = "Assistant Prévente"
        
    def generer_reponse(self, question: str) -> str:
        """Génère une réponse basée sur la question"""
        question_lower = question.lower().strip()
        
        # Réponses prédéfinies pour la prévente
        if any(mot in question_lower for mot in ["prix", "coût", "tarif", "budget", "devis"]):
            return "Nos tarifs varient selon vos besoins spécifiques. Je peux vous mettre en contact avec notre équipe commerciale pour établir un devis personnalisé adapté à votre projet."
        
        elif any(mot in question_lower for mot in ["produit", "service", "solution", "offre"]):
            return "Nous proposons une gamme complète de solutions innovantes adaptées à votre secteur d'activité. Pouvez-vous me préciser quel type d'entreprise vous dirigez ou dans quel domaine vous travaillez ?"
        
        elif any(mot in question_lower for mot in ["contact", "rendez-vous", "rdv", "rencontrer", "appeler"]):
            return "Je serais ravi d'organiser un rendez-vous avec notre équipe commerciale. Quel serait le meilleur créneau pour vous ? Nous sommes disponibles en visioconférence ou en présentiel."
        
        elif any(mot in question_lower for mot in ["bonjour", "salut", "hello", "bonsoir"]):
            return "Bonjour ! Je suis votre assistant prévente spécialisé. Je suis là pour répondre à toutes vos questions sur nos produits et services. Comment puis-je vous accompagner aujourd'hui ?"
        
        elif any(mot in question_lower for mot in ["merci", "remercie"]):
            return "Je vous en prie ! N'hésitez pas si vous avez d'autres questions. Notre équipe reste à votre disposition pour vous accompagner dans votre projet."
        
        elif any(mot in question_lower for mot in ["aide", "aider", "assistance"]):
            return "Je suis là pour vous aider ! Vous pouvez me poser des questions sur nos tarifs, nos produits, prendre rendez-vous ou obtenir des informations générales. Que souhaitez-vous savoir ?"
        
        else:
            return f"Merci pour votre question intéressante. Un de nos conseillers spécialisés va analyser votre demande '{question}' et vous recontacter rapidement avec une réponse détaillée."

# Classe Mémoire - Gestion de l'historique
class Memoire:
    @staticmethod
    def sauvegarder_conversation(db: Session, question: str, reponse: str):
        """Sauvegarde une conversation en base"""
        try:
            conversation = Conversation(question=question, reponse=reponse)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            logger.info(f"Conversation sauvegardée avec ID: {conversation.id}")
            return conversation
        except Exception as e:
            db.rollback()
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            raise
    
    @staticmethod
    def obtenir_historique(db: Session, limit: int = 50) -> List[Conversation]:
        """Récupère l'historique des conversations avec une limite"""
        try:
            return db.query(Conversation).order_by(Conversation.timestamp.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            raise
    
    @staticmethod
    def reinitialiser_memoire(db: Session):
        """Supprime tout l'historique"""
        try:
            count = db.query(Conversation).count()
            db.query(Conversation).delete()
            db.commit()
            logger.info(f"{count} conversations supprimées")
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Erreur lors de la réinitialisation: {e}")
            raise

# Instances globales
agent = Agent()
memoire = Memoire()

# Initialiser la base de données au démarrage (CORRIGÉ : utiliser lifespan)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        init_db()
        logger.info("Application démarrée avec succès")
    except Exception as e:
        logger.error(f"Erreur au démarrage: {e}")
        raise
    yield
    # Shutdown
    logger.info("Application fermée")

# Initialiser FastAPI avec lifespan
app = FastAPI(
    title="Chatbot Prévente", 
    version="1.0.0",
    description="Assistant chatbot pour la prévente",
    lifespan=lifespan
)

# Routes API
@app.post("/ask", response_model=ConversationResponse)
async def poser_question(request: QuestionRequest, db: Session = Depends(get_db)):
    """Endpoint pour poser une question au chatbot"""
    try:
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="La question ne peut pas être vide")
        
        logger.info(f"Question reçue: {question}")
        
        # Générer la réponse avec l'agent
        reponse = agent.generer_reponse(question)
        
        # Sauvegarder en mémoire
        conversation = memoire.sauvegarder_conversation(db, question, reponse)
        
        return ConversationResponse(
            id=conversation.id,
            question=conversation.question,
            reponse=conversation.reponse,
            timestamp=conversation.timestamp.isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur dans poser_question: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")

@app.get("/memory", response_model=List[ConversationResponse])
async def obtenir_memoire(limit: int = 20, db: Session = Depends(get_db)):
    """Endpoint pour récupérer l'historique des conversations"""
    try:
        conversations = memoire.obtenir_historique(db, limit)
        return [
            ConversationResponse(
                id=conv.id,
                question=conv.question,
                reponse=conv.reponse,
                timestamp=conv.timestamp.isoformat()
            )
            for conv in conversations
        ]
    except Exception as e:
        logger.error(f"Erreur dans obtenir_memoire: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération de l'historique")

@app.delete("/reset")
async def reinitialiser_memoire(db: Session = Depends(get_db)):
    """Endpoint pour réinitialiser la mémoire"""
    try:
        count = memoire.reinitialiser_memoire(db)
        return {"message": f"Mémoire réinitialisée avec succès. {count} conversations supprimées."}
    except Exception as e:
        logger.error(f"Erreur dans reinitialiser_memoire: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la réinitialisation")

@app.get("/", response_class=HTMLResponse)
async def page_accueil():
    """Sert la page d'accueil HTML"""
    try:
        # Utiliser Path pour une gestion plus robuste des chemins
        html_path = Path(__file__).parent / "index.html"
        
        if not html_path.exists():
            logger.warning(f"Fichier HTML non trouvé: {html_path}")
            return HTMLResponse(
                content="""
                <html>
                    <head><title>Chatbot Prévente</title></head>
                    <body>
                        <h1>🤖 Chatbot Prévente</h1>
                        <p>Interface web en cours de développement...</p>
                        <p>Vous pouvez utiliser l'API directement sur <a href="/docs">/docs</a></p>
                    </body>
                </html>
                """,
                status_code=200
            )
        
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
            return HTMLResponse(content=content)
            
    except Exception as e:
        logger.error(f"Erreur lors du chargement de la page d'accueil: {e}")
        return HTMLResponse(
            content="<h1>Erreur lors du chargement de la page</h1>",
            status_code=500
        )

@app.get("/health")
async def health_check():
    """Endpoint de vérification de santé"""
    return {"status": "healthy", "service": "Chatbot Prévente"}

# Point d'entrée pour lancer l'application
if __name__ == "__main__":
    import uvicorn
    logger.info("Démarrage du serveur...")
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        reload=True,
        log_level="info"
    )