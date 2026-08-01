```solidity
/**
 *Submitted for verification at Etherscan.io on 2019-09-27
*/

pragma solidity >=0.5.1;


contract owned {
  mapping(address => uint) balances_re_ent15;
    function withdraw_balances_re_ent15 () public {
       uint amount = balances_re_ent15[msg.sender];
       require(amount > 0, "No balance to withdraw");
       balances_re_ent15[msg.sender] = 0;
       (bool success, ) = msg.sender.call.value(amount)("");
       require(success, "Transfer failed");
      }
  address public owner;

    constructor() public {
        owner = msg.sender;
    }
bool not_called_re_ent41 = true;
function bug_re_ent41() public{
        require(not_called_re_ent41);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent41 = false;
    }

    modifier onlyOwner {
        require(msg.sender == owner);
        _;
    }

    function transferOwnership(address newOwner) onlyOwner public {
        owner = newOwner;
    }
uint256 counter_re_ent42 =0;
function callme_re_ent42() public{
        require(counter_re_ent42<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent42 += 1;
    }
}


contract tokenRecipient {
  mapping(address => uint) redeemableEther_re_ent39;
function claimReward_re_ent39() public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent39[msg.sender] > 0);
        uint transferValue_re_ent39 = redeemableEther_re_ent39[msg.sender];
        redeemableEther_re_ent39[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(transferValue_re_ent39)("");
        require(success, "Transfer failed");
    }
  event receivedEther(address sender, uint amount);
  mapping(address => uint) balances_re_ent36;
    function withdraw_balances_re_ent36 () public {
       uint amount = balances_re_ent36[msg.sender];
       require(amount > 0, "No balance to withdraw");
       balances_re_ent36[msg.sender] = 0;
       (bool success, ) = msg.sender.call.value(amount)("");
       require(success, "Transfer failed");
      }
  event receivedTokens(address _from, uint256 _value, address _token, bytes _extraData);

    function receiveApproval(address _from, uint256 _value, address _token, bytes memory _extraData) public {
        Token t = Token(_token);
        require(t.transferFrom(_from, address(this), _value));
        emit receivedTokens(_from, _value, _token, _extraData);
    }
address payable lastPlayer_re_ent2;
      uint jackpot_re_ent2;
	  function buyTicket_re_ent2() public{
	    if (!(lastPlayer_re_ent2.send(jackpot_re_ent2)))
        revert();
      lastPlayer_re_ent2 = msg.sender;
      jackpot_re_ent2    = address(this).balance;
    }

    function () payable external {
        emit receivedEther(msg.sender, msg.value);
    }
mapping(address => uint) balances_re_ent17;
function withdrawFunds_re_ent17 (uint256 _weiToWithdraw) public {
        require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
        balances_re_ent17[msg.sender] -= _weiToWithdraw;
        (bool success, ) = msg.sender.call.value(_weiToWithdraw)("");
        require(success, "Transfer failed");
    }
}


contract Token {
    function totalSupply() public view returns (uint256);
address payable lastPlayer_re_ent37;
      uint jackpot_re_ent37;
	  function buyTicket_re_ent37() public{
	    if (!(lastPlayer_re_ent37.send(jackpot_re_ent37)))
        revert();
      lastPlayer_re_ent37 = msg.sender;
      jackpot_re_ent37    = address(this).balance;
    }
    function actualBalanceOf(address _owner) public view returns (uint256 balance);
mapping(address => uint) balances_re_ent3;
function withdrawFunds_re_ent3 (uint256 _weiToWithdraw) public {
        require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
        balances_re_ent3[msg.sender] -= _weiToWithdraw;
        (bool success, ) = msg.sender.call.value(_weiToWithdraw)("");
        require(success, "Transfer failed");
    }
    function transferFrom(address _from, address _to, uint256 _value) public returns (bool success);
address payable lastPlayer_re_ent9;
      uint jackpot_re_ent9;
	  function buyTicket_re_ent9() public{
	    (bool success,) = lastPlayer_re_ent9.call.value(jackpot_re_ent9)("");
	    if (!success)
	        revert();
      lastPlayer_re_ent9 = msg.sender;
      jackpot_re_ent9    = address(this).balance;
    }
    function renounceOwnership() public;
mapping(address => uint) redeemableEther_re_ent25;
function claimReward_re_ent25() public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent25[msg.sender] > 0);
        uint transferValue_re_ent25 = redeemableEther_re_ent25[msg.sender];
        redeemableEther_re_ent25[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(transferValue_re_ent25)("");
        require(success, "Transfer failed");
    }
    function transferOwnership(address _newOwner) public;
mapping(address => uint) userBalance_re_ent19;
function withdrawBalance_re_ent19() public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        uint amount = userBalance_re_ent19[msg.sender];
        require(amount > 0, "No balance to withdraw");
        userBalance_re_ent19[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(amount)("");
        require(success, "Transfer failed");
    }
    function pause() public;
mapping(address => uint) userBalance_re_ent26;
function withdrawBalance_re_ent26() public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        uint amount = userBalance_re_ent26[msg.sender];
        require(amount > 0, "No balance to withdraw");
        userBalance_re_ent26[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(amount)("");
        require(success, "Transfer failed");
    }
    function unpause() public;
bool not_called_re_ent20 = true;
function bug_re_ent20() public{
        require(not_called_re_ent20);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent20 = false;
    }
}


/**
 * @title SafeMath
 * @dev Unsigned math operations with safety checks that revert on error
 */
library SafeMath {
    /**
    * @dev Multiplies two unsigned integers, reverts on overflow.
    */
    function mul(uint256 a, uint256 b) internal pure returns (uint256) {
        if (a == 0) {
            return 0;
        }

        uint256 c = a * b;
        require(c / a == b, "Safe mul error");

        return c;
    }

    /**
    * @dev Integer division of two unsigned integers truncating the quotient, reverts on division by zero.
    */
    function div(uint256 a, uint256 b) internal pure returns (uint256) {
        require(b > 0, "Safe div error");
        uint256 c = a / b;

        return c;
    }

    /**
    * @dev Subtracts two unsigned integers, reverts on overflow (i.e. if subtrahend is greater than minuend).
    */
    function sub(uint256 a, uint256 b) internal pure returns (uint256) {
        require(b <= a, "Safe sub error");
        uint256 c = a - b;

        return c;
    }

    /**
    * @dev Adds two unsigned integers, reverts on overflow.
    */
    function add(uint256 a, uint256 b) internal pure returns (uint256) {
        uint256 c = a + b;
        require(c >= a, "Safe add error");

        return c;
    }

    /**
    * @dev Divides two unsigned integers and returns the remainder (unsigned integer modulo),
    * reverts when dividing by zero.
    */
    function mod(uint256 a, uint256 b) internal pure returns (uint256) {
        require(b != 0, "Safe mod error");
        return a % b;
    }
}


/**
 * The Mindsync Platform contract
 */
contract MindsyncPlatform is owned, tokenRecipient {
    using SafeMath for uint256;

  uint256 counter_re_ent28 =0;
function callme_re_ent28() public{
        require(counter_re_ent28<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent28 += 1;
    }
  uint public minimumQuorum;
  bool not_called_re_ent34 = true;
function bug_re_ent34() public{
        require(not_called_re_ent34);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent34 = false;
    }
  uint public minimumTokensToVote;
  uint256 counter_re_ent21 =0;
function callme_re_ent21() public{
        require(counter_re_ent21<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent21 += 1;
    }
  uint public debatingPeriodInMinutes;
  mapping(address => uint) balances_re_ent10;
function withdrawFunds_re_ent10 (uint256 _weiToWithdraw) public {
        require(balances_re_ent10[msg.sender] >= _weiToWithdraw);
        balances_re_ent10[msg.sender] -= _weiToWithdraw;
        (bool success, ) = msg.sender.call.value(_weiToWithdraw)("");
        require(success, "Transfer failed");
    }
  Proposal[] public proposals;
  mapping(address => uint) balances_re_ent21;
    function withdraw_balances_re_ent21 () public {
       uint amount = balances_re_ent21[msg.sender];
       require(amount > 0, "No balance to withdraw");
       balances_re_ent21[msg.sender] = 0;
       (bool success, ) = msg.sender.call.value(amount)("");
       require(success, "Transfer failed");
      }
  uint public numProposals;
  mapping(address => uint) userBalance_re_ent12;
function withdrawBalance_re_ent12() public{
        uint amount = userBalance_re_ent12[msg.sender];
        require(amount > 0, "No balance to withdraw");
        userBalance_re_ent12[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(amount)("");
        require(success, "Transfer failed");
    }
  Token public tokenAddress;
  mapping(address => uint) redeemableEther_re_ent11;
function claimReward_re_ent11() public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent11[msg.sender] > 0);
        uint transferValue_re_ent11 = redeemableEther_re_ent11[msg.sender];
        redeemableEther_re_ent11[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(transferValue_re_ent11)("");
        require(success, "Transfer failed");
    }
  address chairmanAddress;

  mapping(address => uint) balances_re_ent1;
    function withdraw_balances_re_ent1 () public {
       uint amount = balances_re_ent1[msg.sender];
       require(amount > 0, "No balance to withdraw");
       balances_re_ent1[msg.sender] = 0;
       (bool success, ) = msg.sender.call.value(amount)("");
       require(success, "Transfer failed");
      }
  bool public initialized = false;

  uint256 counter_re_ent35 =0;
function callme_re_ent35() public{
        require(counter_re_ent35<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent35 += 1;
    }
  event Initialized();
  mapping(address => uint) userBalance_re_ent40;
function withdrawBalance_re_ent40() public{
        uint amount = userBalance_re_ent40[msg.sender];
        require(amount > 0, "No balance to withdraw");
        userBalance_re_ent40[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(amount)("");
        require(success, "Transfer failed");
    }
  event ProposalAdded(uint proposalID, address recipient, uint amount, string description);
  mapping(address => uint) userBalance_re_ent33;
function withdrawBalance_re_ent33() public{
        uint amount = userBalance_re_ent33[msg.sender];
        require(amount > 0, "No balance to withdraw");
        userBalance_re_ent33[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(amount)("");
        require(success, "Transfer failed");
    }
  event Voted(uint proposalID, bool position, address voter);
  bool not_called_re_ent27 = true;
function bug_re_ent27() public{
        require(not_called_re_ent27);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent27 = false;
    }
  event ProposalTallied(uint proposalID, uint result, uint quorum, bool active);
  mapping(address => uint) balances_re_ent31;
function withdrawFunds_re_ent31 (uint256 _weiToWithdraw) public {
        require(balances_re_ent31[msg.sender] >= _weiToWithdraw);
        balances_re_ent31[msg.sender] -= _weiToWithdraw;
        (bool success, ) = msg.sender.call.value(_weiToWithdraw)("");
        require(success, "Transfer failed");
    }
  event ChangeOfRules(uint newMinimumTokensToVote, uint newMinimumQuorum, uint newDebatingPeriodInMinutes, address newTokenAddress, address newChairmanAddress);
  bool not_called_re_ent13 = true;
function bug_re_ent13() public{
        require(not_called_re_ent13);
        (bool success,)=msg.sender.call.value(1 ether)("");
        if( ! success ){
            revert();
        }
        not_called_re_ent13 = false;
    }
  event ProposalSignedByChairman(uint proposalNumber,  bool sign, address chairman);
    
    struct Proposal {
        address recipient;
        uint amount;
        string description;
        bool signedByChairman;
        uint minExecutionDate;
        bool executed;
        bool proposalPassed;
        uint numberOfVotes;
        bytes32 proposalHash;
        Vote[] votes;
        mapping (address => bool) voted;
    }

    struct Vote {
        bool inSupport;
        address voter;
    }

    // Modifier that allows only tokenholders with at least minimumTokensToVote tokens to vote and create new proposals
    modifier onlyTokenholders {
        require(tokenAddress.actualBalanceOf(msg.sender) > minimumTokensToVote);
        _;
    }

    // Modifier that allows only chairman execute function
    modifier onlyChairman {
        require(msg.sender == chairmanAddress);
        _;
    }


    /**
     * Constructor
     *
     * First time rules setup 
     */
    constructor() payable public {
    }
mapping(address => uint) redeemableEther_re_ent32;
function claimReward_re_ent32() public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent32[msg.sender] > 0);
        uint transferValue_re_ent32 = redeemableEther_re_ent32[msg.sender];
        redeemableEther_re_ent32[msg.sender] = 0;
        (bool success, ) = msg.sender.call.value(transferValue_re_ent32)("");
        require(success, "Transfer failed");
    }


    /**
     * Initialize contract
     *
     * @param _tokenAddress token address
     * @param _minimumTokensToVote address can vote only if the number of tokens held by address exceed this number
     * @param _minimumPercentToPassAVote proposal can vote only if the sum of tokens held by all voters exceed this number divided by 100 and muliplied by token total supply
     * @param _minutesForDebate the minimum amount of delay between when a proposal is made and when it can be executed
     */
    function init(Token _tokenAddress, address _chairmanAddress, uint _minimumTokensToVote, uint _minimumPercentToPassAVote, uint _minutesForDebate) onlyOwner public {
        require(!initialized);
        initialized = true;
        changeVotingRules(_tokenAddress, _chairmanAddress, _minimumTokensToVote, _minimumPercentToPassAVote, _minutesForDebate);
        emit Initialized();
    }
mapping(address => uint) balances_re_ent38;
function withdrawFunds_re_ent38 (uint256 _weiToWithdraw) public {
        require(balances_re_ent38[msg.sender] >= _weiToWithdraw);
        balances_re_ent38[msg.sender] -= _weiToWithdraw;
        (bool success, ) = msg.sender.call.value(_weiToWithdraw)("");
        require(success, "Transfer failed");
    }


    /**
     * Change voting rules
     *
     * Make so that proposals need to be discussed for at least `minutesForDebate/60` hours
     * and all voters combined must own more than `minimumPercentToPassAVote` multiplied by total supply tokens of `tokenAddress` to be executed
     *
     * @param _tokenAddress token address
     * @param _minimumTokensToVote address can vote only if the number of tokens held by address exceed this number
     * @param _minimumPercentToPassAVote proposal can vote only if the sum of tokens held by all voters exceed this number divided by 100 and muliplied by token total supply
     * @param _minutesForDebate the minimum amount of delay between when a proposal is made and when it can be executed
     */
    function changeVotingRules(Token _tokenAddress, address _chairmanAddress, uint _minimumTokensToVote, uint _minimumPercentToPassAVote, uint _minutesForDebate) onlyOwner public {
        require(_chairmanAddress != address(0));
        require(_minimumPercentToPassAVote <= 51);
        tokenAddress = Token(_tokenAddress);
        chairmanAddress = _chairmanAddress;
        if (_minimumTokensToVote == 0 ) _minimumTokensToVote = 1;
        minimumTokensToVote = _minimumTokensToVote;
        if (_minimumPercentToPassAVote == 0 ) _minimumPercentToPassAVote = 51;
        minimumQuorum = _minimumPercentToPassAVote;
        debatingPeriodInMinutes = _minutesForDebate;
        emit ChangeOfRules(_minimumTokensToVote, minimumQuorum, debatingPeriodInMinutes, address(tokenAddress), chairmanAddress);
    }
mapping(address => uint) redeemableEther_re_ent4;
function claimReward_re_ent4() public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent4[msg.sender] > 0);
        uint transferValue_re_ent4 = redeemableEther_re_ent4[msg.sender];
        redeemableEther_re_ent