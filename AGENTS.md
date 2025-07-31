the app will be community driven and the goal is to track green data (user provided), updates to that green data, and to give users a way to publish tasting notes from samples. the data from greens will be pdfs for now but later may be excel documents, etc.. they can also enter green offerings manually, so we want a nice UI for users to be able to do this. I am thinking this should be a Flask app, with something nice that integrates well for the frontend as we will eventually want nice modals for uploading data. the app will be community driven: users will suggest changes and if enough suggest changes it will be implemented. users will have karma that is "built up" from having their changes accepted by the community (the karma is a hidden metric). we need to track what they suggest and what gets accepted throughout time to audit this data. eventually we may have other data points that are community driven. some other features: 

- a system that tracks green data uploaded from users. 
- a system that allows users to input tasting notes
- implement database for users, green data storage, any other database tables you think are required
- green data does change
- user registration
- user login
- admin interface with login (flask-admin?)

suggest other important features as well and implement them.