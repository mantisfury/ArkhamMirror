import reflex as rx
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..services.llm_service import chat_with_llm
from ..services.search_service import hybrid_search

logger = logging.getLogger(__name__)

# Add project root to path for central config
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config import DATABASE_URL
from app.arkham.services.db.models import Document

# Database setup from central config
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class ChatState(rx.State):
    """State for LLM chat interface with RAG support."""

    messages: List[Dict[str, str]] = []
    current_input: str = ""
    is_typing: bool = False
    selected_doc_id: Optional[int] = None
    selected_doc_label: str = "All Files"
    document_options: Dict[str, Optional[int]] = {"All Files": None}

    @rx.var
    def document_option_labels(self) -> List[str]:
        """Get list of document labels for select dropdown."""
        return list(self.document_options.keys())

    def on_load(self):
        """Load available documents on component mount."""
        self.load_documents()

    def load_documents(self):
        """Load document list from database."""
        session = Session()
        try:
            docs = session.query(Document).order_by(Document.created_at.desc()).all()
            self.document_options = {"All Files": None}
            for doc in docs:
                label = f"{doc.title} (ID: {doc.id})"
                self.document_options[label] = doc.id
        except Exception as e:
            logger.error(f"Error loading documents: {e}")
        finally:
            session.close()

    def set_selected_doc(self, value: str):
        """Update selected document for context filtering."""
        self.selected_doc_label = value
        self.selected_doc_id = self.document_options.get(value, None)

    def set_input(self, val: str):
        self.current_input = val

    async def send_message(self):
        if not self.current_input:
            return

        # Save user query before clearing input
        user_query = self.current_input

        # Add user message
        user_msg = {"role": "user", "content": user_query}
        self.messages.append(user_msg)
        self.current_input = ""
        self.is_typing = True

        # Yield to update UI
        yield

        try:
            # Phase 1.5: RAG Integration - Search for relevant context
            context_chunks = []
            context_text = ""

            if user_query.strip():
                # Build allowed_doc_ids filter
                allowed_doc_ids = None
                if self.selected_doc_id:
                    allowed_doc_ids = [self.selected_doc_id]

                # Perform hybrid search
                context_chunks = hybrid_search(
                    query=user_query, allowed_doc_ids=allowed_doc_ids, limit=5
                )

                # Format context with citations
                if context_chunks:
                    session = Session()
                    try:
                        # Fetch document titles for citations
                        doc_ids = {
                            chunk.get("doc_id")
                            for chunk in context_chunks
                            if chunk.get("doc_id")
                        }
                        doc_titles = {}
                        if doc_ids:
                            docs = (
                                session.query(Document.id, Document.title)
                                .filter(Document.id.in_(doc_ids))
                                .all()
                            )
                            doc_titles = {doc_id: title for doc_id, title in docs}
                    finally:
                        session.close()

                    # Build context text with citations
                    context_parts = []
                    for chunk in context_chunks:
                        doc_title = doc_titles.get(
                            chunk.get("doc_id"), "Unknown Document"
                        )
                        chunk_id = chunk.get("id", "?")
                        chunk_text = chunk.get("text", "")
                        context_parts.append(
                            f"[Source: {doc_title} | Chunk ID: {chunk_id}]\n{chunk_text}"
                        )
                    context_text = "\n\n".join(context_parts)

            # Build message with forensic investigator system prompt
            system_prompt = (
                "You are an expert forensic investigator analyzing a database of documents. "
                "Your goal is to answer questions accurately based ONLY on the provided context snippets. "
                "CRITICAL INSTRUCTION: When you cite information, you MUST include BOTH the Document Title and the Chunk ID. "
                "Format your citations exactly like this: [Source: Document Title | Chunk ID: 123]. "
                "If the answer is not in the context, say 'I cannot find that information in the provided documents.'"
            )

            # Construct messages for LLM
            llm_messages = [{"role": "system", "content": system_prompt}]

            # Add context if available
            if context_text:
                llm_messages.append(
                    {
                        "role": "user",
                        "content": f"Context:\n{context_text}\n\nQuestion: {user_query}",
                    }
                )
            else:
                llm_messages.append({"role": "user", "content": user_query})

            # Call LLM
            response_content = chat_with_llm(
                llm_messages, temperature=0.3, max_tokens=1000
            )

            # Handle generator response
            if hasattr(response_content, "__iter__") and not isinstance(
                response_content, str
            ):
                full_response = ""
                for chunk in response_content:
                    full_response += chunk
                response_content = full_response

            self.messages.append(
                {"role": "assistant", "content": str(response_content)}
            )

        except Exception as e:
            self.messages.append({"role": "system", "content": f"Error: {str(e)}"})

        self.is_typing = False


def chat_interface() -> rx.Component:
    """Chat interface component with RAG support."""
    return rx.vstack(
        # Document selector dropdown
        rx.hstack(
            rx.text("Context:", font_weight="bold", min_width="80px"),
            rx.select(
                ChatState.document_option_labels,
                value=ChatState.selected_doc_label,
                on_change=ChatState.set_selected_doc,
                width="100%",
            ),
            rx.button(
                rx.icon(tag="refresh-cw", size=16),
                on_click=ChatState.load_documents,
                size="2",
                variant="soft",
            ),
            width="100%",
            spacing="2",
        ),
        # Chat messages area
        rx.scroll_area(
            rx.vstack(
                rx.foreach(
                    ChatState.messages,
                    lambda msg: rx.box(
                        rx.text(msg["content"], white_space="pre-wrap"),
                        bg=rx.cond(
                            msg["role"] == "user",
                            "blue.600",
                            rx.cond(msg["role"] == "system", "red.700", "gray.700"),
                        ),
                        color="white",
                        padding="3",
                        border_radius="lg",
                        align_self=rx.cond(msg["role"] == "user", "end", "start"),
                        max_width="80%",
                    ),
                ),
                spacing="3",
                align_items="stretch",
                width="100%",
            ),
            height="400px",
            width="100%",
            padding="4",
            bg="gray.900",
            border_radius="md",
        ),
        # Input area
        rx.hstack(
            rx.input(
                placeholder="Ask a question about your documents...",
                value=ChatState.current_input,
                on_change=ChatState.set_input,
                width="100%",
            ),
            rx.button(
                rx.icon(tag="send"),
                on_click=ChatState.send_message,
                loading=ChatState.is_typing,
            ),
            width="100%",
        ),
        width="100%",
        spacing="4",
        on_mount=ChatState.on_load,
    )
