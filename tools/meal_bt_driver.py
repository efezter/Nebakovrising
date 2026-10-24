"""Small cooperative BT test driver for the mod's shared meal functions.

Engine animation and navigation nodes are mocks; ExecuteLua runs the actual mod.
This checks ordering/cancellation contracts, not in-game animation correctness.
"""
import re
import xml.etree.ElementTree as ET


class MealBtDriver:
    def __init__(self, lua, path, entity, token, blocked_seats=(), blocked_bowl=False, blocked_standing=False):
        self.lua = lua
        self.entity = entity
        self.token = token
        self.functions = {t.get("name"): t for t in ET.parse(path).getroot()}
        self.blocked_seats = set(blocked_seats)
        self.blocked_bowl = blocked_bowl
        self.blocked_standing = blocked_standing
        self.stance = "sitting"
        self.events = []
        self.run_code = lua.eval("function(code, entity, data) local f = assert(loadstring('return function(entity, data) ' .. code .. ' end')); return f()(entity, data) end")
        self.run_condition = lua.eval("function(expr, data) local f = assert(loadstring('return function(data) return ' .. expr .. ' end')); return f()(data) end")
        self.generator = self.function("nebakovrising_meal_at_table", token)

    def condition(self, expression, data):
        expression = re.sub(r"\$([A-Za-z_][A-Za-z_0-9]*)", r"data.\1", expression)
        return bool(self.run_condition(expression.replace("&", " and ").replace("|", " or "), data))

    def function(self, name, token):
        tree = self.functions[name]
        data = self.lua.table(activityToken=token)
        for variable in tree.find("Variables"):
            value = variable.get("values", "")
            data[variable.get("name")] = value == "true" if value in ("true", "false") else None
        return (yield from self.node(tree.find("Root/Behavior")[0], data))

    def sequence(self, nodes, data):
        for child in nodes:
            if not (yield from self.node(child, data)):
                return False
        return True

    def node(self, node, data):
        tag = node.tag
        if tag == "ExecuteLua":
            code = node.get("code", "")
            self.run_code(code, self.entity, data)
            if "OnMealEaten" in code:
                self.events.append(("eaten", self.stance))
            if "FinishMeal" in code:
                self.events.append(("release", self.stance))
            return True
        if tag == "Success":
            return True
        if tag == "Fail":
            return False
        if tag == "Sequence":
            return (yield from self.sequence(node, data))
        if tag.startswith("Function_"):
            return (yield from self.function(tag.removeprefix("Function_"), data.activityToken))
        if tag == "IfCondition":
            if self.condition(node.get("condition"), data):
                return (yield from self.sequence(node, data))
            return node.get("failOnCondition") != "true"
        if tag == "IfElseCondition":
            branch = node.find("Then" if self.condition(node.get("condition"), data) else "Else")
            return (yield from self.sequence(branch, data))
        if tag == "While":
            while self.condition(node.get("condition"), data):
                result = yield from self.sequence(node, data)
                if not result and node.get("propagateChildFail") == "true":
                    return False
                yield
            return node.get("doFail") != "true"
        if tag == "Loop":
            while True:
                if not (yield from self.sequence(node, data)):
                    return False
                yield
        if tag == "Wait":
            duration = node.get("duration").strip("'")
            if duration == "-1":
                while True:
                    yield
            seconds = float(duration[:-2]) / 1000 if duration.endswith("ms") else float(duration.removesuffix("s"))
            deadline = self.lua.globals().clock + seconds
            while self.lua.globals().clock < deadline:
                yield
            return node.get("doFail") != "true"
        if tag == "Parallel":
            generators = [self.node(child, data) for child in node]
            finished = {}
            try:
                while True:
                    for i, generator in enumerate(generators):
                        if i in finished:
                            continue
                        try:
                            next(generator)
                        except StopIteration as result:
                            finished[i] = result.value
                            if not result.value and node.get("failureMode") == "Any":
                                return False
                            if result.value and node.get("successMode") == "Any":
                                return True
                    if len(finished) == len(generators):
                        return all(finished.values())
                    yield
            finally:
                for generator in generators:
                    generator.close()
        if tag == "SuppressFailure":
            yield from self.sequence(node, data)
            return True
        if tag == "HandContentElement":
            if self.blocked_bowl:
                while True:
                    yield
            return (yield from self.sequence(node.find("Exec"), data))
        if tag == "AddLinkElement":
            wuid = data.mealBenchWuid
            old = self.lua.globals().occupants[wuid]
            if node.get("tag") == "'benchOccupant'":
                self.lua.globals().occupants[wuid] = self.lua.table_from([self.entity.this.id])
            try:
                return (yield from self.sequence(node, data))
            finally:
                if node.get("tag") == "'benchOccupant'":
                    self.lua.globals().occupants[wuid] = old
        if tag == "StanceElement":
            if node.get("stance") == "standing" and self.blocked_standing:
                while True:
                    yield
            if node.get("stance") == "sitting" and data.mealBenchWuid in self.blocked_seats:
                while True:
                    yield
            yield
            self.stance = node.get("stance")
            return (yield from self.sequence(node, data))
        if tag == "StanceCheck":
            return self.stance == node.get("stance")
        if tag in ("WaitAction", "UnstanceAction"):
            yield
            return True
        if tag == "UrgencyDecorator":
            return (yield from self.sequence(node, data))
        if tag == "InstantSendMessageToNPC":
            self.events.append((node.get("type"), self.stance))
            return True
        raise AssertionError(f"Unsupported test node: {tag}")

    def tick(self):
        self.lua.globals().clock += 0.5
        self.lua.globals().nebakovrising.CastleUtils.ActivityHeartbeat(self.entity.this.id, self.token)
        try:
            next(self.generator)
            return None
        except StopIteration as result:
            return result.value

    def until(self, predicate, max_ticks=400):
        for _ in range(max_ticks):
            result = self.tick()
            if predicate():
                return
            if result is not None:
                raise AssertionError(f"BT ended early: {result}; {self.events}")
        raise AssertionError(f"BT did not reach expected state: {self.events}")
