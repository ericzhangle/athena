from __future__ import annotations

import re


class KnowledgeIngestionEngine:
    """Extracts provisional claims from short knowledge articles.

    This is intentionally rule-based for now. The goal is not perfect NLP; it is
    to turn paragraph knowledge into traceable claims that Athena can question.
    """

    SURFACE_ALIASES = {
        "fruit": "Fruit",
        "plastic apple": "PlasticApple",
        "vitamin c": "VitaminC",
        "dietary fiber": "DietaryFiber",
        "natural sugar": "NaturalSugar",
        "gut health": "GutHealth",
        "immune function": "Immunity",
        "body function": "BodyFunction",
        "food safety": "FoodSafety",
        "toy car": "ToyCar",
        "水果": "Fruit",
        "苹果": "Apple",
        "香蕉": "Banana",
        "西瓜": "Watermelon",
        "葡萄": "Grape",
        "芒果": "Mango",
        "橙子": "Orange",
        "橘子": "Tangerine",
        "塑料苹果": "PlasticApple",
        "塑料": "Plastic",
        "维生素C": "VitaminC",
        "维生素c": "VitaminC",
        "维生素": "Vitamin",
        "膳食纤维": "DietaryFiber",
        "矿物质": "Mineral",
        "钾": "Potassium",
        "钾元素": "Potassium",
        "水分": "Water",
        "糖分": "NaturalSugar",
        "天然糖分": "NaturalSugar",
        "消化": "Digestion",
        "肠道健康": "GutHealth",
        "免疫力": "Immunity",
        "免疫功能": "Immunity",
        "能量": "Energy",
        "营养物质": "Nutrient",
        "营养成分": "Nutrient",
        "身体功能": "BodyFunction",
        "身体健康": "Health",
        "过敏": "Allergy",
        "卫生": "FoodSafety",
        "汽车": "Car",
        "玩具汽车": "ToyCar",
        "玩具车": "ToyCar",
        "车辆": "Vehicle",
        "金属": "Metal",
    }

    STOP_CONCEPTS = {
        "A",
        "An",
        "And",
        "Are",
        "Be",
        "But",
        "Can",
        "Different",
        "Directly",
        "For",
        "Generally",
        "Into",
        "Is",
        "It",
        "Kind",
        "Many",
        "May",
        "More",
        "Not",
        "Of",
        "One",
        "Other",
        "Some",
        "Something",
        "The",
        "This",
        "To",
        "Usually",
        "What",
    }

    def extract_claims(self, text: str) -> list[dict[str, object]]:
        claims: list[dict[str, object]] = []
        for sentence in self._sentences(text):
            claims.extend(self._claims_from_sentence(sentence))
        return self._dedupe_claims(claims)

    def _sentences(self, text: str) -> list[str]:
        parts = re.split(r"[。！？!?；;\.]\s*", text)
        return [part.strip() for part in parts if part.strip()]

    def _claims_from_sentence(self, sentence: str) -> list[dict[str, object]]:
        claims: list[dict[str, object]] = []
        concepts = self._concepts_in(sentence)
        claims.extend(self._generic_relation_claims(sentence, concepts))
        claims.extend(self._generic_attribute_claims(sentence, concepts))

        for concept in concepts:
            claims.append(self._concept_presence(concept, sentence))

        return claims

    def _generic_relation_claims(self, sentence: str, concepts: list[str]) -> list[dict[str, object]]:
        claims: list[dict[str, object]] = []
        if len(concepts) < 2:
            return claims

        last_subject: str | None = None
        for clause in self._clauses(sentence):
            clause_concepts = self._concepts_in(clause)
            if len(clause_concepts) >= 2:
                last_subject = clause_concepts[0]
            elif len(clause_concepts) == 1 and last_subject:
                target = clause_concepts[0]
                if target != last_subject and self._clause_negates_target(clause, target):
                    claims.append(self._relation(last_subject, "is-not-a", target, sentence))
            for subject in clause_concepts:
                for target in clause_concepts:
                    if subject == target:
                        continue
                    if self._mentions_is_not_a(clause, subject, target):
                        claims.append(self._relation(subject, "is-not-a", target, sentence))
                    elif self._mentions_is_a(clause, subject, target):
                        claims.append(self._relation(subject, "is-a", target, sentence))
                    if self._mentions_contains(clause, subject, target):
                        claims.append(self._relation(subject, "contains", target, sentence))
                    if self._mentions_supports(clause, subject, target):
                        claims.append(self._relation(subject, "supports", target, sentence))
                    if self._mentions_makes(clause, subject, target):
                        claims.append(self._relation(subject, "can-be-made-into", target, sentence))
                    if self._mentions_triggers(clause, subject, target):
                        claims.append(self._relation(subject, "may_trigger", target, sentence))
                    if self._mentions_related_to(clause, subject, target):
                        claims.append(self._relation(subject, "related-to", target, sentence))
                    if self._mentions_affects(clause, subject, target):
                        claims.append(self._relation(subject, "can_affect", target, sentence))

        for subject in concepts:
            for target in concepts:
                if subject != target and self._mentions_made_of(sentence, subject, target):
                    claims.append(self._relation(subject, "made-of", target, sentence))

        return claims

    def _generic_attribute_claims(self, sentence: str, concepts: list[str]) -> list[dict[str, object]]:
        claims: list[dict[str, object]] = []
        for concept in concepts:
            if self._mentions_edible(sentence, concept):
                claims.append(
                    self._attribute(
                        concept,
                        "edibility",
                        f"{concept} is described as edible in the text.",
                        sentence,
                    )
                )
            if self._mentions_inedible(sentence, concept):
                claims.append(
                    self._attribute(
                        concept,
                        "edibility",
                        f"{concept} is described as not edible or not food in the text.",
                        sentence,
                    )
                )
        return claims

    def _clauses(self, sentence: str) -> list[str]:
        return [part.strip() for part in re.split(r"[，,、；;]", sentence) if part.strip()]

    def _clause_negates_target(self, clause: str, target: str) -> bool:
        lowered = clause.lower()
        if "不是" not in clause and "not" not in lowered and "isn't" not in lowered:
            return False
        return any(re.search(re.escape(form), clause, flags=re.IGNORECASE) for form in self._surface_forms(target))

    def _concepts_in(self, sentence: str) -> list[str]:
        found: list[tuple[int, str]] = []
        found_concepts = set()
        occupied_spans: list[tuple[int, int]] = []
        normalized_sentence = self._surface_key(sentence)
        aliases = sorted(self.SURFACE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
        for raw, canonical in aliases:
            if canonical in found_concepts:
                continue
            raw_key = self._surface_key(raw)
            if not raw_key:
                continue
            start = normalized_sentence.find(raw_key)
            if start < 0:
                continue
            span = (start, start + len(raw_key))
            if any(not (span[1] <= existing[0] or span[0] >= existing[1]) for existing in occupied_spans):
                continue
            found.append((span[0], canonical))
            found_concepts.add(canonical)
            occupied_spans.append(span)
        for position, concept in self._dynamic_concepts(sentence):
            if concept in found_concepts:
                continue
            if concept in self.STOP_CONCEPTS:
                continue
            found.append((position, concept))
            found_concepts.add(concept)
        return [canonical for _, canonical in sorted(found, key=lambda item: item[0])]

    def _dynamic_concepts(self, sentence: str) -> list[tuple[int, str]]:
        found: list[tuple[int, str]] = []
        patterns = [
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+(?:an?|one)\s+(?P<object>[A-Za-z][A-Za-z0-9 _-]{0,40}?)(?=$|,|;|\band\b|\bbut\b)",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+not\s+(?:an?|one)?\s*(?P<object>[A-Za-z][A-Za-z0-9 _-]{0,40}?)(?=$|,|;|\band\b|\bbut\b)",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+(?:contains?|includes?|has)\s+(?P<object>[A-Za-z][A-Za-z0-9 _-]{0,40}?)(?=$|,|;|\band\b|\bbut\b)",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+(?:supports?|helps?|maintains?|affects?|influences?|triggers?|causes?)\s+(?P<object>[A-Za-z][A-Za-z0-9 _-]{0,40}?)(?=$|,|;|\band\b|\bbut\b)",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+(?:made|built|created)\s+(?:of|from)\s+(?P<object>[A-Za-z][A-Za-z0-9 _-]{0,40}?)(?=$|,|;|\band\b|\bbut\b)",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+related\s+to\s+(?P<object>[A-Za-z][A-Za-z0-9 _-]{0,40}?)(?=$|,|;|\band\b|\bbut\b)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, sentence, flags=re.IGNORECASE):
                for group in ["subject", "object"]:
                    raw = self._clean_surface(match.group(group))
                    concept = self._canonicalize_surface(raw)
                    if concept and concept not in self.STOP_CONCEPTS:
                        found.append((match.start(group), concept))
        for match in re.finditer(r"\b[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+\b", sentence):
            concept = self._canonicalize_surface(match.group(0))
            if concept and concept not in self.STOP_CONCEPTS:
                found.append((match.start(), concept))
        attribute_subject_patterns = [
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+can\s+(?:usually\s+)?be\s+eaten\b",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+edible\b",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+not\s+edible\b",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+not\s+food\b",
            r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+cannot\s+be\s+eaten\b",
        ]
        for pattern in attribute_subject_patterns:
            for match in re.finditer(pattern, sentence, flags=re.IGNORECASE):
                concept = self._canonicalize_surface(match.group("subject"))
                if concept and concept not in self.STOP_CONCEPTS:
                    found.append((match.start("subject"), concept))
        for match in re.finditer(r"\b(?P<subject>[A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+is\s+(?:something|anything|a\s+thing)\s+", sentence, flags=re.IGNORECASE):
            concept = self._canonicalize_surface(match.group("subject"))
            if concept and concept not in self.STOP_CONCEPTS:
                found.append((match.start("subject"), concept))
        return found

    def _clean_surface(self, value: str) -> str:
        value = re.sub(r"\b(the|a|an|some|many|different|other)\b", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"\b(can|usually|directly|also|for|by|with|that|to|as)\b", " ", value, flags=re.IGNORECASE)
        return " ".join(value.strip(" ,.;:!?").split())

    def _canonicalize_surface(self, value: str) -> str:
        cleaned = self._clean_surface(value)
        if not cleaned:
            return ""
        alias = self._canonical_from_alias(cleaned)
        if alias:
            return alias
        words = re.split(r"[\s_\-]+", cleaned)
        if len(words) == 1:
            word = words[0]
            if word.lower().endswith("s") and len(word) > 3:
                word = word[:-1]
            return word[:1].upper() + word[1:]
        return "".join(word[:1].upper() + word[1:] for word in words if word)

    def _canonical_from_alias(self, value: str) -> str | None:
        value_key = self._surface_key(value)
        for raw, canonical in self.SURFACE_ALIASES.items():
            if self._surface_key(raw) == value_key:
                return canonical
        if value_key.endswith("s"):
            singular_key = value_key[:-1]
            for raw, canonical in self.SURFACE_ALIASES.items():
                if self._surface_key(raw) == singular_key:
                    return canonical
        return None

    def _surface_key(self, text: str) -> str:
        return re.sub(r"[\s_\-]+", "", text).casefold()

    def _surface_forms(self, concept: str) -> list[str]:
        forms = [concept]
        spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", concept).strip()
        if spaced and spaced != concept:
            forms.append(spaced)
        forms.append(concept.casefold())
        if spaced:
            forms.append(spaced.casefold())
        for raw, canonical in self.SURFACE_ALIASES.items():
            if canonical == concept:
                forms.append(raw)
        return sorted(set(forms), key=len, reverse=True)

    def _mentions_is_a(self, sentence: str, subject: str, target: str) -> bool:
        if self._pair_pattern(sentence, subject, target, [r"是(?:一)?种", r"属于"]):
            return True
        return self._english_direct_pair(
            sentence,
            subject,
            target,
            [
                r"is\s+(?:an?|one)\s+",
                r"is\s+(?:an?\s+)?(?:kind|type|class)\s+of\s+",
                r"belongs\s+to\s+",
                r"is\s+classified\s+as\s+(?:an?\s+)?",
            ],
        )

    def _mentions_is_not_a(self, sentence: str, subject: str, target: str) -> bool:
        if self._pair_pattern(sentence, subject, target, [r"不是(?:一)?种", r"不是"]):
            return True
        return self._english_direct_pair(
            sentence,
            subject,
            target,
            [
                r"is\s+not\s+(?:an?|one)?\s*",
                r"isn't\s+(?:an?|one)?\s*",
                r"are\s+not\s+(?:an?|one)?\s*",
            ],
        )

    def _mentions_contains(self, sentence: str, subject: str, target: str) -> bool:
        return self._pair_pattern(sentence, subject, target, [r"含有", r"富含", r"包含", r"\bcontains?\b", r"\bincludes?\b", r"\bhas\b", r"\brich\s+in\b"])

    def _mentions_supports(self, sentence: str, subject: str, target: str) -> bool:
        return self._pair_pattern(sentence, subject, target, [r"有助于", r"帮助", r"支持", r"维持", r"\bsupports?\b", r"\bhelps?\b", r"\baids?\b", r"\bmaintains?\b"])

    def _mentions_made_of(self, sentence: str, subject: str, target: str) -> bool:
        for subject_form in self._surface_forms(subject):
            for target_form in self._surface_forms(target):
                subject_pattern = f"(?<![\\u4e00-\\u9fffA-Za-z]){re.escape(subject_form)}"
                same_clause = (
                    f"{subject_pattern}[^，,；;。]*[由用]"
                    f"[^，,；;。]*{re.escape(target_form)}[^，,；;。]*(制成|做成|制作)"
                )
                contrast_clause = (
                    f"{subject_pattern}[^。；;]*不是[^。；;]*而是[由用]"
                    f"[^。；;]*{re.escape(target_form)}[^。；;]*(制成|做成|制作)"
                )
                english_clause = (
                    f"{subject_pattern}[^\\.。；;]*(is|are)[^\\.。；;]*(made|built|created)"
                    f"[^\\.。；;]*(of|from)[^\\.。；;]*{re.escape(target_form)}"
                )
                if (
                    re.search(same_clause, sentence, flags=re.IGNORECASE)
                    or re.search(contrast_clause, sentence, flags=re.IGNORECASE)
                    or re.search(english_clause, sentence, flags=re.IGNORECASE)
                ):
                    return True
        return False

    def _mentions_makes(self, sentence: str, subject: str, target: str) -> bool:
        return self._pair_pattern(sentence, subject, target, [r"制成", r"制作成", r"做成", r"\bmade\s+into\b", r"\bprocessed\s+into\b", r"\bturned\s+into\b"])

    def _mentions_triggers(self, sentence: str, subject: str, target: str) -> bool:
        return self._pair_pattern(sentence, subject, target, [r"引起", r"触发", r"导致", r"可能会对", r"\btriggers?\b", r"\bcauses?\b", r"\bleads?\s+to\b"])

    def _mentions_related_to(self, sentence: str, subject: str, target: str) -> bool:
        return self._pair_pattern(sentence, subject, target, [r"和", r"与", r"\brelated\s+to\b", r"\bassociated\s+with\b", r"\bconnected\s+to\b"], suffixes=[r"有关", r"相关", ""])

    def _mentions_affects(self, sentence: str, subject: str, target: str) -> bool:
        return self._pair_pattern(sentence, subject, target, [r"\baffects?\b", r"\binfluences?\b", r"\bcan\s+affect\b", r"\bcan\s+influence\b"])

    def _mentions_edible(self, sentence: str, subject: str) -> bool:
        return self._subject_attribute_pattern(
            sentence,
            subject,
            [
                r"\bis\s+something\s+edible\b",
                r"\bis\s+edible\b",
                r"\bcan\s+be\s+eaten\b",
                r"\bcan\s+usually\s+be\s+eaten\b",
                r"\bcan\s+eat\b",
                r"\beaten\s+directly\b",
            ],
        )

    def _mentions_inedible(self, sentence: str, subject: str) -> bool:
        return self._subject_attribute_pattern(
            sentence,
            subject,
            [
                r"\bis\s+not\s+food\b",
                r"\bis\s+not\s+edible\b",
                r"\bcannot\s+be\s+eaten\b",
                r"\bcan\s+not\s+be\s+eaten\b",
                r"\bcan't\s+be\s+eaten\b",
            ],
        )

    def _subject_attribute_pattern(self, sentence: str, subject: str, predicates: list[str]) -> bool:
        for subject_form in self._surface_forms(subject):
            for predicate in predicates:
                pattern = rf"\b{re.escape(subject_form)}\b[^\.。；;，,]*{predicate}"
                if re.search(pattern, sentence, flags=re.IGNORECASE):
                    return True
        return False

    def _pair_pattern(
        self,
        sentence: str,
        subject: str,
        target: str,
        connectors: list[str],
        suffixes: list[str] | None = None,
    ) -> bool:
        suffixes = suffixes or [""]
        for subject_form in self._surface_forms(subject):
            for target_form in self._surface_forms(target):
                for connector in connectors:
                    for suffix in suffixes:
                        if re.search(
                            f"{re.escape(subject_form)}.*{connector}.*{re.escape(target_form)}.*{suffix}",
                            sentence,
                            flags=re.IGNORECASE,
                        ):
                            return True
        return False

    def _english_direct_pair(
        self,
        sentence: str,
        subject: str,
        target: str,
        connectors: list[str],
    ) -> bool:
        for subject_form in self._surface_forms(subject):
            for target_form in self._surface_forms(target):
                for connector in connectors:
                    pattern = (
                        rf"\b{re.escape(subject_form)}\b[^\.。；;，,]*\b{connector}"
                        rf"\b{re.escape(target_form)}\b"
                    )
                    if re.search(pattern, sentence, flags=re.IGNORECASE):
                        return True
        return False

    def _attribute(self, subject: str, name: str, value: str, sentence: str) -> dict[str, object]:
        return {
            "kind": "attribute",
            "subject": subject,
            "predicate": name,
            "object": value,
            "attribute_name": name,
            "attribute_value": value,
            "statement": sentence,
            "questions": self._questions_for(subject, name, value),
        }

    def _relation(self, subject: str, relation_type: str, target: str, sentence: str) -> dict[str, object]:
        return {
            "kind": "relation",
            "subject": subject,
            "predicate": relation_type,
            "object": target,
            "relation_type": relation_type,
            "target": target,
            "statement": sentence,
            "questions": self._questions_for_relation(subject, relation_type, target),
        }

    def _concept_presence(self, concept: str, sentence: str) -> dict[str, object]:
        return {
            "kind": "concept",
            "subject": concept,
            "predicate": "mentioned_in_knowledge_text",
            "object": "mentioned",
            "statement": sentence,
            "questions": self._questions_for_new_concept(concept),
        }

    def _questions_for(self, subject: str, name: str, value: str) -> list[dict[str, str]]:
        questions = []
        if name in {"identity", "origin"}:
            questions.append({
                "question": f"{subject} 的这个身份或来源在所有情况下都成立吗？有没有例外？",
                "reason": "knowledge_claim_needs_boundary",
            })
        if name in {"caution", "safety_practice"}:
            questions.append({
                "question": f"{subject} 的这个注意事项适用于哪些情况？什么时候最重要？",
                "reason": "safety_claim_needs_condition",
            })
        if name in {"water_content", "taste", "edibility"}:
            questions.append({
                "question": f"{subject} 的 {name} 是普遍特征、常见特征，还是只适用于部分例子？",
                "reason": "attribute_scope_unclear",
            })
        return questions

    def _questions_for_relation(self, subject: str, relation_type: str, target: str) -> list[dict[str, str]]:
        if relation_type in {"is-a", "is-not-a"}:
            return []
        return [
            {
                "question": f"{subject} {relation_type} {target} 这件事为什么重要？它会带来什么影响？",
                "reason": "relation_mechanism_unclear",
            },
            {
                "question": f"{target} 是什么？它有哪些关键特性？",
                "reason": "related_concept_needs_identity",
            },
        ]

    def _questions_for_new_concept(self, concept: str) -> list[dict[str, str]]:
        return [
            {
                "question": f"{concept} 是什么？它和当前学习主题有什么关系？",
                "reason": "mentioned_concept_needs_identity",
            }
        ]

    def _dedupe_claims(self, claims: list[dict[str, object]]) -> list[dict[str, object]]:
        seen = set()
        deduped = []
        for claim in claims:
            key = (claim["kind"], claim["subject"], claim["predicate"], claim["object"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(claim)
        return deduped
