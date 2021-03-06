package indexengine;

import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.apache.lucene.search.IndexSearcher;
import org.apache.lucene.search.Query;
import org.apache.lucene.search.ScoreDoc;
import org.apache.lucene.search.TopDocs;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;

public class DocumentRetriever {

	private String indexDirectory;
	
	private static final Logger logger = Logger.getLogger(DocumentRetriever.class.getName());
	
	public DocumentRetriever(){
		configure();
	}
	
	private void configure(){
		
		Properties indexConfiguration = new Properties();
		ClassLoader cl = this.getClass().getClassLoader();	
		try (InputStream in = cl.getResourceAsStream("conf/IndexConfig.properties")) {
			indexConfiguration.load(in);
			this.indexDirectory = indexConfiguration.getProperty("indexDirectory");
		} catch (FileNotFoundException fnfe) {
			logger.log(Level.SEVERE, "Error configuring DocumentRetriever object" , fnfe);
			System.exit(0);
		} catch (IOException ioe) {
			logger.log(Level.SEVERE, "Error configuring DocumentRetriever object" , ioe);
			System.exit(0);
		}
	}
	
	private IndexSearcher createSearcher() throws IOException {
		Directory dir = FSDirectory.open(Paths.get(this.indexDirectory));
		IndexReader reader = DirectoryReader.open(dir);
		IndexSearcher searcher = new IndexSearcher(reader);
		return searcher;
	}
		
	private TopDocs searchByContent(String queryInputString, IndexSearcher searcher, int numberOfDocs) throws Exception {
		QueryParser queryParser = new QueryParser("paper_text", new StandardAnalyzer());
		Query textQuery = queryParser.parse(queryInputString);
		TopDocs hits = searcher.search(textQuery, numberOfDocs);
		return hits;
	}
	
	private TopDocs searchByTitle(String queryInputString, IndexSearcher searcher, int numberOfDocs) throws Exception {
		QueryParser queryParser = new QueryParser("paper_title", new StandardAnalyzer());
		Query textQuery = queryParser.parse(queryInputString);
		TopDocs hits = searcher.search(textQuery, numberOfDocs);
		return hits;
	}
	
	public List<Integer> searchDocumentsByContent(String queryInputString, int numberOfDocs) throws Exception {
		IndexSearcher searcher = createSearcher();
		TopDocs foundDocs = searchByContent(queryInputString, searcher, numberOfDocs);
		
	   	List<Integer> selectedDocuments = new ArrayList<Integer>();    	
		//System.out.println("Number of found documents: " + foundDocs.totalHits);
	   	int counter = 1;
		for (ScoreDoc scoreDoc: foundDocs.scoreDocs){
			Document document = searcher.doc(scoreDoc.doc);
			//System.out.println(String.format(document.get("pdf_name")));
			String docId = document.get("id");
			String pdfName = document.get("pdf_name");
			try {
				selectedDocuments.add(Integer.parseInt(docId));
				//System.out.println("Counter: " + counter + ", Doc id: " + docId + ", score:" + scoreDoc.score + ", pdf_name: " + pdfName);
			} catch (NumberFormatException nfe){
				logger.log(Level.INFO, "Document id: " + docId + " couldn't be added to list of documents", nfe);
			}
			counter++;
		}
		
		return selectedDocuments;
	}
		
	public List<Integer> searchDocumentsByTitle(String queryInputString, int numberOfDocs) throws Exception {
		IndexSearcher searcher = createSearcher();
		TopDocs foundDocs = searchByTitle(queryInputString, searcher, numberOfDocs);
		
	   	List<Integer> selectedDocuments = new ArrayList<Integer>();    	
		for (ScoreDoc scoreDoc: foundDocs.scoreDocs){
			Document document = searcher.doc(scoreDoc.doc);
			//System.out.println(String.format(document.get("pdf_name")));
			String docId = document.get("id");
			try {
				selectedDocuments.add(Integer.parseInt(docId));
			} catch (NumberFormatException nfe){
				logger.log(Level.INFO, "Document id: " + docId + " couldn't be added to list of documents", nfe);
			}
		}
		return selectedDocuments;
	}

	
	public static void main(String[] args) throws Exception {
				
		DocumentRetriever documentRetriever = new DocumentRetriever();
		String queryInputString = "fredholm kernels";
		List<Integer> selectedDocuments = documentRetriever.searchDocumentsByContent(queryInputString, 10);
		//List<Integer> selectedDocuments = documentRetriever.searchDocumentsByTitle(queryInputString, 10);
		
		// Print selected documents
		
		for (Integer id: selectedDocuments){
			System.out.println(id);
		}
	}
	// (2381, 2371, 5918, 6037, 6475, 4570, 3757, 922, 1516, 2315);

}
