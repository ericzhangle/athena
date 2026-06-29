from __future__ import annotations


class MockInquiryProvider:
    """A replaceable reference provider for the first inquiry loop.

    Later this can be swapped for DeepSeek, web search, a local document index,
    or multiple providers. Returned text is reference evidence, not final truth.
    """

    def answer(self, question: str) -> dict[str, str]:
        lowered = question.lower()
        if "grape" in lowered or "葡萄" in question:
            text = (
                "Grape is a fruit. Grapes can usually be eaten directly. "
                "Grape can be made into juice, raisins, and wine. "
                "Grape contains water and some vitamins."
            )
        elif "orange" in lowered or "橙子" in question:
            text = (
                "Orange is a fruit. Orange belongs to the citrus group. "
                "Orange can usually be eaten directly or made into juice. "
                "Orange contains VitaminC."
            )
        elif "tangerine" in lowered or "橘子" in question:
            text = (
                "Tangerine is a fruit. Tangerine belongs to the citrus group. "
                "Tangerine can usually be eaten directly. Tangerine contains VitaminC."
            )
        elif "allergy" in lowered or "过敏" in question:
            text = (
                "Allergy is not a fruit. Allergy is a body reaction to some substances. "
                "Mango, pollen, medicine, or other foods may trigger Allergy. "
                "Allergy can affect health, but severity varies by person."
            )
        elif "mango" in lowered or "芒果" in question:
            text = (
                "Mango is a fruit. Mango can usually be eaten directly. "
                "Mango contains Vitamin and DietaryFiber. Mango may trigger Allergy for some people."
            )
        elif "foodsafety" in lowered or "food safety" in lowered or "卫生" in question:
            text = (
                "FoodSafety is not a fruit. FoodSafety is a practice for reducing risk when handling food. "
                "Washing fruit supports FoodSafety."
            )
        elif "plasticapple" in lowered or "塑料苹果" in question:
            text = (
                "PlasticApple is not a fruit. PlasticApple is made of Plastic. "
                "PlasticApple can look like Apple, but it is not food."
            )
        elif "plastic" in lowered or "塑料" in question:
            text = (
                "Plastic is a material, not a fruit. Plastic is not food. "
                "Plastic can be used to make containers, packaging, or toys."
            )
        elif "water" in lowered or "水分" in question:
            text = (
                "Water is not a fruit. Water is a substance that supports body function. "
                "Fruit can contain Water. Water is related to Health."
            )
        elif "fruit" in lowered or "水果" in question:
            text = (
                "Fruit is a food category. Fruit is not a nutrient. Many fruits can be eaten directly. "
                "Fruit can contain Vitamin, VitaminC, DietaryFiber, Mineral, Water, and NaturalSugar. "
                "Fruit may trigger Allergy for some people. Fruit washing supports FoodSafety."
            )
        elif "vitaminc" in lowered or "维生素c" in question.lower():
            text = (
                "VitaminC is a nutrient, not a fruit. "
                "Many fruits contain VitaminC. VitaminC supports Immunity and helps maintain Health."
            )
        elif "vitamin" in lowered or "维生素" in question:
            text = (
                "Vitamin is a nutrient, not a fruit. "
                "Fruit can contain different vitamins. Vitamin supports BodyFunction and Health."
            )
        elif "nutrient" in lowered or "营养" in question:
            text = (
                "Nutrient is not a fruit. Nutrient is a general category for substances that support BodyFunction and Health. "
                "Vitamin is a nutrient. Mineral is a nutrient. DietaryFiber is a nutrient. Potassium is a nutrient."
            )
        elif "mineral" in lowered or "矿物质" in question:
            text = (
                "Mineral is a nutrient, not a fruit. "
                "Fruit can contain minerals. Mineral supports BodyFunction."
            )
        elif "potassium" in lowered or "钾" in question:
            text = (
                "Potassium is a mineral, not a fruit. "
                "Banana contains Potassium. Potassium supports BodyFunction."
            )
        elif "dietaryfiber" in lowered or "膳食纤维" in question:
            text = (
                "DietaryFiber is a nutrient, not a fruit. "
                "Fruit can contain DietaryFiber. DietaryFiber supports Digestion and GutHealth."
            )
        elif "digestion" in lowered or "消化" in question:
            text = (
                "Digestion is not a fruit. Digestion is a body process for handling food and nutrients. "
                "DietaryFiber supports Digestion. Digestion is related to Health."
            )
        elif "immunity" in lowered or "免疫" in question:
            text = (
                "Immunity is not a fruit. Immunity is a body ability for resisting disease. "
                "VitaminC supports Immunity. Immunity is related to Health."
            )
        elif "energy" in lowered or "能量" in question:
            text = (
                "Energy is not a fruit. Energy is needed for body activity. "
                "NaturalSugar can affect Energy. Energy is related to BodyFunction."
            )
        elif "health" in lowered or "身体健康" in question:
            text = (
                "Health is not a fruit. Health is a condition of the body. "
                "Nutrient is related to Health. Digestion is related to Health. Immunity is related to Health. Energy is related to Health."
            )
        elif "naturalsugar" in lowered or "天然糖分" in question or "糖分" in question:
            text = (
                "NaturalSugar is a food component, not a fruit. "
                "Fruit can contain NaturalSugar. NaturalSugar can affect Energy."
            )
        else:
            text = (
                "This question needs more evidence. Treat the concept as temporarily unknown, "
                "record possible relations to known concepts, and continue looking for evidence."
            )
        return {
            "provider": "mock_reference_provider",
            "question": question,
            "answer": text,
        }
