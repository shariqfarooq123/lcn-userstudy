import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
import datasets
import json
import uuid
import random
from dataclasses import dataclass
from PIL import Image

st.set_page_config(layout="wide")
st.markdown('''
<style>
[data-testid="stMarkdownContainer"] ul{
    padding-left:40px;
}
</style>
''', unsafe_allow_html=True)

ALL_METHODS = ["ours", "controlnet"]
caption_col = "caption"
USER_PREFFERENCES_COLLECTION = "Responses"

@dataclass
class Sample:
	caption: str
	ours: Image.Image
	controlnet: Image.Image
	sample_id: str
	condition: Image.Image
	order: tuple = ('ours', 'controlnet')

	def to_tuple(self):
		return tuple([self.order, self.caption] + [getattr(self, method) for method in self.order])


def load_data():
	with st.spinner("Loading ..."):
		data_bd = datasets.load_dataset('shariqfarooq/lcn_bd', split='train')
		data_box = datasets.load_dataset('shariqfarooq/lcn_box', split='train')
	return data_bd, data_box

def get_state(*args):
	out = [getattr(st.session_state, arg) for arg in args]
	if len(out) == 1:
		return out[0]
	else:
		return out

def set_state(**kwargs):
	for key, value in kwargs.items():
		setattr(st.session_state, key, value)



def upload_preference(user_id, sample_id, dataset, choice):
	db : firestore.Client
	db, user_id = get_state("db", "user_id")
	col = db.collection(USER_PREFFERENCES_COLLECTION)
	col.add({'user_id': user_id, 'sample_id': sample_id, 'dataset': dataset, 'choice': choice})
	

def display_preferences():
	# debug only
	db, user_id = get_state("db", "user_id")
	preferences = db.collection(USER_PREFFERENCES_COLLECTION).where("user_id", "==", user_id).stream()
	# preferences = db.collection("preferences").stream()
	for pref in preferences:
		st.write(pref.to_dict())


def make_checkboxes_exclusive(selected_key, method, sample_id, dataset):
	for key, value in st.session_state.items():
		if key.startswith("checkbox_") and (f"_{sample_id}" in key) and (f"_{dataset}" in key) and (key != selected_key) and value:
			st.session_state[key] = False

def clear_checkboxes():
	for key, value in st.session_state.items():
		if key.startswith("checkbox_"):
			st.session_state[key] = False

# def submit_button_label(methods):
# 	if any(st.session_state[f"checkbox_{method}"] for method in methods):
# 		return "Submit"
# 	else:
# 		return "I'm not sure"



def has_filled_all():
	for sample_id in st.session_state.all_sample_ids:
		# we have atleast one true for each sample_id
		if not any(st.session_state[k] for k in st.session_state if k.startswith(f"checkbox_") and f"_{sample_id}_" in k):
			return False
	return True
	
def on_submit():
	for key, value in st.session_state.items():
		if key.startswith("checkbox_") and value:
			method = key.split("_")[1]
			sample_id = key.split("_")[2]
			dataset = key.split("_")[3]
			# print(f"Selected {method} for {sample_id}")
			# with st.spinner("Submit ..."):
			upload_preference(user_id=st.session_state.user_id, sample_id=sample_id, dataset=dataset, choice=method)
	
	set_state(is_submitted=True)
	st.balloons()


def preference_ui():
	st.markdown(
	"""
	# Section 1
	## Instructions
	You will be provided with:
	- a textual description (in blue),
	- one guide image: This is a black-and-white image which describes the shape and position of walls, ceiling and floor,
	- and two test images.

	Please select the image that you prefer for the given textual description and the guide by clicking the checkbox below it.
	""")
	for i, sample in enumerate(st.session_state.data_bd):
		order, caption, im1, im2 = sample.to_tuple()
		st.info(caption)
		items = [(method, im) for method, im in zip(order, [im1, im2])]
		cols = st.columns(3)
		cols[0].image(sample.condition)
		# random.shuffle(items)
		for col, (method, image) in zip(cols[1:], items):
			with col:
				st.image(image)
				st.checkbox("", key=f"checkbox_{method}_{sample.sample_id}_bd", on_change=make_checkboxes_exclusive, kwargs=dict(selected_key=f"checkbox_{method}_{sample.sample_id}_bd", method=method, sample_id=sample.sample_id, dataset='bd'))

		st.divider()
	st.markdown(
	"""
	# Section 2
	## Instructions
	You will be provided with
	- a textual description (in blue),
	- one guide image: This time, guide image represents position, size and orientation of objects in the 3D space,
	- and two test images.

	Please select the image that you prefer for the given textual description and the guide by clicking the checkbox below it.
	"""
	)
	for i, sample in enumerate(st.session_state.data_box):
		order, caption, im1, im2 = sample.to_tuple()
		st.info(caption)
		items = [(method, im) for method, im in zip(order, [im1, im2])]
		cols = st.columns(3)
		cols[0].image(sample.condition)
		# random.shuffle(items)
		for col, (method, image) in zip(cols[1:], items):
			with col:
				st.image(image)
				st.checkbox("", key=f"checkbox_{method}_{sample.sample_id}_box", on_change=make_checkboxes_exclusive, kwargs=dict(selected_key=f"checkbox_{method}_{sample.sample_id}_box", method=method, sample_id=sample.sample_id, dataset='box'))
		st.divider()

	has_filled = has_filled_all()
	label = "Please respond to all questions" if not has_filled else "Submit"
	st.button(label, on_click=on_submit, kwargs=dict(), disabled=not has_filled_all())


if not hasattr(st.session_state, "user_id"):
	key_dict = json.loads(st.secrets["textkey"])
	creds = service_account.Credentials.from_service_account_info(key_dict)
	db = firestore.Client(credentials=creds)
	data_bd, data_box = load_data()
	# choose random 5 samples from each dataset
	inds = random.sample(range(len(data_bd)), 5)
	data_bd = data_bd.select(inds)

	data_bd = [Sample(caption=x[caption_col], ours=x['ours'], controlnet=x['controlnet'], order=random.sample(ALL_METHODS, len(ALL_METHODS)), sample_id=x['idd'], condition=x['condition']) for x in data_bd]

	inds = random.sample(range(len(data_box)), 5)
	data_box = data_box.select(inds)
	data_box = [Sample(caption=x[caption_col], ours=x['ours'], controlnet=x['controlnet'], order=random.sample(ALL_METHODS, len(ALL_METHODS)), sample_id=x['idd'], condition=x['condition']) for x in data_box]


	all_sample_ids = [x.sample_id for x in data_bd] + [x.sample_id for x in data_box]
	set_state(db=db, data_bd=data_bd, data_box=data_box, user_id=str(uuid.uuid4()), is_submitted=False, all_sample_ids=all_sample_ids)

if st.session_state.is_submitted:
	st.write("## Thank you for participating in our study!")
else:
	st.title("Welcome! Thank you for participating in our study.")
	"""
	This study has two sections (5 questions each). Pick the choice that you prefer for each question.
	Please click the 'Submit' button after completing both sections.
	"""
	preference_ui()

